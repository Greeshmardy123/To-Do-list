import os
# Ensure the instance directory exists before anything else
if not os.path.exists('instance'):
    os.makedirs('instance')

basedir = os.path.abspath(os.path.dirname(__file__))

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'instance', 'to_do_list.sqlite')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.example.com'  # Replace with your SMTP server
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@example.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'your_password'           # Replace with your email password
app.config['MAIL_DEFAULT_SENDER'] = 'your_email@example.com'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # type: ignore[attr-defined]
mail = Mail(app)

ATTACHMENT_FOLDER = os.path.join('static', 'attachments')
os.makedirs(ATTACHMENT_FOLDER, exist_ok=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    tasks = db.relationship('Task', backref='user', lazy=True)
    profile_pic = db.Column(db.String(256), default=None)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    priority = db.Column(db.String(50))
    category = db.Column(db.String(100))
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recurrence = db.Column(db.String(20), default=None)  # None, Daily, Weekly, Monthly
    subtasks = db.relationship('Subtask', backref='task', lazy=True)
    attachments = db.relationship('Attachment', backref='task', lazy=True)

class Subtask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    filepath = db.Column(db.String(512), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def home():
    return redirect(url_for('tasks'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register'))
        user = User()
        user.username = username
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/tasks')
@login_required
def tasks():
    # Get filter/sort/search parameters
    status = request.args.get('status')
    priority = request.args.get('priority')
    category = request.args.get('category')
    sort = request.args.get('sort', 'due_date')
    search = request.args.get('search')

    # Build query
    query = Task.query.filter_by(user_id=current_user.id)
    if status == 'complete':
        query = query.filter_by(completed=True)
    elif status == 'incomplete':
        query = query.filter_by(completed=False)
    if priority:
        query = query.filter_by(priority=priority)
    if category:
        query = query.filter_by(category=category)
    if search:
        query = query.filter(
            (Task.title.ilike(f'%{search}%')) |
            (Task.description.ilike(f'%{search}%'))
        )
    # Sorting
    if sort == 'priority':
        query = query.order_by(Task.priority)
    elif sort == 'title':
        query = query.order_by(Task.title)
    else:
        query = query.order_by(Task.due_date)

    user_tasks = query.all()
    # Find due/overdue tasks for in-app notification
    due_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.completed == False,
        Task.due_date != None,
        Task.due_date <= date.today()
    ).all()
    return render_template('tasks.html', tasks=user_tasks, status=status, priority=priority, category=category, sort=sort, search=search, due_tasks=due_tasks)

@app.route('/tasks/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        due_date = request.form.get('due_date')
        priority = request.form.get('priority')
        category = request.form.get('category')
        recurrence = request.form.get('recurrence')
        due_date_obj = datetime.strptime(due_date, '%Y-%m-%d') if due_date else None
        new_task = Task()
        new_task.title = title
        new_task.description = description
        new_task.due_date = due_date_obj
        new_task.priority = priority
        new_task.category = category
        new_task.user_id = current_user.id
        new_task.recurrence = recurrence if recurrence else None
        db.session.add(new_task)
        db.session.commit()
        flash('Task added successfully!')
        return redirect(url_for('tasks'))
    return render_template('add_task.html')

@app.route('/tasks/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        task.title = request.form['title']
        task.description = request.form.get('description')
        due_date = request.form.get('due_date')
        task.due_date = datetime.strptime(due_date, '%Y-%m-%d') if due_date else None
        task.priority = request.form.get('priority')
        task.category = request.form.get('category')
        task.recurrence = request.form.get('recurrence') if request.form.get('recurrence') else None
        # Handle subtasks
        subtask_titles = request.form.getlist('subtask_title')
        subtask_ids = request.form.getlist('subtask_id')
        subtask_completed = request.form.getlist('subtask_completed')
        for i, sub_id in enumerate(subtask_ids):
            sub = Subtask.query.get(int(sub_id))
            if sub and sub.task_id == task.id:
                sub.title = subtask_titles[i]
                sub.completed = str(sub_id) in subtask_completed
        new_subtask_title = request.form.get('new_subtask_title')
        if new_subtask_title:
            new_sub = Subtask()
            new_sub.title = new_subtask_title
            new_sub.completed = False
            new_sub.task_id = task.id
            db.session.add(new_sub)
        # Handle attachments
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename:
                filename = secure_filename(file.filename)
                filepath = os.path.join(ATTACHMENT_FOLDER, filename)
                file.save(filepath)
                new_attachment = Attachment()
                new_attachment.filename = filename
                new_attachment.filepath = filepath
                new_attachment.task_id = task.id
                db.session.add(new_attachment)
        db.session.commit()
        flash('Task updated successfully!')
        return redirect(url_for('tasks'))
    subtasks = Subtask.query.filter_by(task_id=task.id).all()
    attachments = Attachment.query.filter_by(task_id=task.id).all()
    return render_template('edit_task.html', task=task, subtasks=subtasks, attachments=attachments)

@app.route('/tasks/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted successfully!')
    return redirect(url_for('tasks'))

@app.route('/tasks/toggle/<int:task_id>', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    task.completed = not task.completed
    db.session.commit()
    flash('Task status updated!')
    return redirect(url_for('tasks'))

@app.route('/api/tasks/toggle/<int:task_id>', methods=['POST'])
@login_required
def api_toggle_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    task.completed = not task.completed
    db.session.commit()
    # If task is now complete and is recurring, create the next occurrence
    if task.completed and task.recurrence and task.due_date:
        from datetime import timedelta
        next_due = None
        if task.recurrence == 'Daily':
            next_due = task.due_date + timedelta(days=1)
        elif task.recurrence == 'Weekly':
            next_due = task.due_date + timedelta(weeks=1)
        elif task.recurrence == 'Monthly':
            next_month = task.due_date.month % 12 + 1
            year = task.due_date.year + (task.due_date.month // 12)
            day = min(task.due_date.day, 28)
            next_due = task.due_date.replace(year=year, month=next_month, day=day)
        if next_due:
            new_task = Task()
            new_task.title = task.title
            new_task.description = task.description
            new_task.due_date = next_due
            new_task.priority = task.priority
            new_task.category = task.category
            new_task.user_id = task.user_id
            new_task.recurrence = task.recurrence
            db.session.add(new_task)
            db.session.commit()
    return jsonify({
        'success': True,
        'completed': task.completed,
        'task_id': task.id,
        'message': 'Task status updated!'
    })

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
PROFILE_PIC_FOLDER = os.path.join('static', 'profile_pics')
os.makedirs(PROFILE_PIC_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        new_username = request.form.get('username')
        new_email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        # Update username
        if new_username and new_username != current_user.username:
            if User.query.filter_by(username=new_username).first():
                flash('Username already taken.')
                return redirect(url_for('profile'))
            current_user.username = new_username
            db.session.commit()
            flash('Username updated successfully!')
        # Update email
        if new_email and new_email != current_user.email:
            if User.query.filter_by(email=new_email).first():
                flash('Email already in use.')
                return redirect(url_for('profile'))
            current_user.email = new_email
            db.session.commit()
            flash('Email updated successfully!')
        # Update password
        if new_password:
            if not current_user.check_password(current_password):
                flash('Current password is incorrect.')
                return redirect(url_for('profile'))
            if new_password != confirm_password:
                flash('New passwords do not match.')
                return redirect(url_for('profile'))
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password updated successfully!')
        # Profile picture upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(PROFILE_PIC_FOLDER, filename)
                file.save(filepath)
                current_user.profile_pic = filename
                db.session.commit()
                flash('Profile picture updated!')
            elif file and file.filename:
                flash('Invalid file type for profile picture.')
        return redirect(url_for('profile'))
    return render_template('profile.html')

def send_task_reminders():
    users = User.query.filter(User.email != None).all()
    for user in users:
        tasks_due = Task.query.filter(
            Task.user_id == user.id,
            Task.completed == False,
            Task.due_date != None,
            Task.due_date <= date.today()
        ).all()
        if tasks_due:
            task_list = '\n'.join([
                f"- {task.title} (Due: {task.due_date.strftime('%Y-%m-%d')})" for task in tasks_due
            ])
            msg = Message(
                subject="Task Reminder: Tasks Due or Overdue",
                recipients=[user.email],
                body=f"Hello {user.username},\n\nThe following tasks are due or overdue:\n\n{task_list}\n\nPlease log in to your to-do list app to manage your tasks."
            )
            mail.send(msg)

@app.route('/send_reminders')
def send_reminders_route():
    send_task_reminders()
    return 'Reminders sent (if any tasks were due)!'

@app.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html')

@app.route('/api/tasks/calendar')
@login_required
def api_tasks_calendar():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    events = []
    for task in tasks:
        if task.due_date:
            events.append({
                'id': task.id,
                'title': task.title + (' (Done)' if task.completed else ''),
                'start': task.due_date.strftime('%Y-%m-%d'),
                'color': '#28a745' if task.completed else '#007bff',
                'allDay': True
            })
    return jsonify(events)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 