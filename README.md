# Advanced To-Do List App

A feature-rich Flask web application for efficient task management with user authentication, file attachments, recurring tasks, and calendar integration.

## ✨ Key Features

- 🔐 **User Authentication** - Secure login/registration system
- 📝 **Task Management** - Create, edit, delete tasks with categories and priorities
- 🔄 **Advanced Features** - Recurring tasks, subtasks, file attachments
- 📅 **Calendar View** - Visual task timeline with due date tracking
- 🔍 **Smart Search** - Filter and sort tasks by status, priority, category
- 📱 **Responsive Design** - Mobile-friendly Bootstrap 5 interface

## 🚀 Quick Start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Setup database**
   ```bash
   python -c "from app import app, db; app.app_context().push(); db.create_all()"
   ```

3. **Run the app**
   ```bash
   python app.py
   ```

4. **Access at** `http://localhost:5000`

## 🛠️ Tech Stack

- **Backend**: Flask, SQLAlchemy
- **Frontend**: Bootstrap 5, HTML/CSS
- **Database**: SQLite
- **Auth**: Flask-Login

## 📋 Requirements

- Python 3.7+
- Flask and dependencies (see requirements.txt)

---

**Perfect for personal task organization and productivity! 🎯** 