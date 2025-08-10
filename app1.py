import os
import csv
import io
import time
from flask import Flask, render_template_string, request, redirect, url_for, flash, session, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from fpdf import FPDF  # Added for PDF generation
from sqlalchemy import or_
from datetime import datetime, time, date

# --- App Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'HRISHABHADMIN2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///contest.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Define your secret token somewhere in your app, e.g. right below app config





# --- Path Configuration (FIX FOR DEPLOYMENT) ---
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

# --- Database Configuration ---
database_url = os.environ.get('DATABASE_URL')
if database_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace("postgres://", "postgresql://", 1)
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'local.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Mail Configuration (placeholders) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = None
app.config['MAIL_PASSWORD'] = None
app.config['MAIL_DEFAULT_SENDER'] = None

# --- Initialize Extensions ---
db = SQLAlchemy(app)
mail = Mail(app)

# --- Database Models ---
RESET_TOKEN = "myUltraSecretResetToken123!"

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

@app.route('/reset_admin_password/<token>')
def reset_admin_password(token):
    if token != RESET_TOKEN:
        return "Unauthorized", 403
    admin = Admin.query.filter_by(username='admin').first()
    if admin:
        admin.set_password('newStrongPassword123')
        db.session.commit()
        return "Admin password reset successfully"
    return "Admin user not found"

class Contest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    date = db.Column(db.Date, nullable=False)
    test_time = db.Column(db.Time, nullable=True)
    syllabus = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    publish_results = db.Column(db.Boolean, default=False, nullable=False)
    students = db.relationship('Student', backref='contest', lazy=True, cascade="all, delete-orphan")

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    college = db.Column(db.String(150), nullable=False, default='NIT Nagaland')
    branch = db.Column(db.String(50), nullable=False)
    graduation_year = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default='Pending', nullable=False)
    test_link = db.Column(db.String(200), nullable=True)
    score = db.Column(db.Integer, nullable=True)
    contest_id = db.Column(db.Integer, db.ForeignKey('contest.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('email', 'contest_id', name='_email_contest_uc'),)

class ContestSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(300), nullable=True)

# --- PDF Generation Helper Class ---
class PDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 15)
        self.cell(0, 10, 'CodeFest - Student Score Report', 0, 1, 'C')
        self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
    def create_table(self, table_data, title='', data_size=10, title_size=12):
        self.set_font('helvetica', 'B', title_size)
        self.cell(0, 10, title, 0, 1, 'C')
        self.ln(4)
        self.set_font('helvetica', 'B', data_size)
        line_height = self.font_size * 2
        col_widths = {'Rank': 15, 'Name': 50, 'Email': 65, 'Branch': 25, 'Score': 20}
        for col_name in table_data[0]:
            self.cell(col_widths[col_name], line_height, col_name, border=1, align='C')
        self.ln(line_height)
        self.set_font('helvetica', '', data_size)
        for row in table_data[1:]:
            for i, datum in enumerate(row):
                self.cell(col_widths[table_data[0][i]], line_height, str(datum), border=1, align='L')
            self.ln(line_height)

# --- CREATE TABLES on startup ---
with app.app_context():
    db.create_all()

# --- HTML Templates ---

LAYOUT_TEMPLATE = """
<!DOCTYPE html><html lang="en" class=""><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }} - Coding Contest</title><script src="https://cdn.tailwindcss.com"></script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script>
    if (localStorage.getItem('color-theme') === 'dark' || (!('color-theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark')
    }
</script>
<style>body { font-family: 'Poppins', sans-serif; } .form-step { display: none; } .form-step-active { display: block; }
.fancy-text { background: linear-gradient(90deg, #4f46e5, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent;}</style></head>
<body class="bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-200 transition-colors duration-300">
<nav class="bg-white/80 dark:bg-gray-800/80 backdrop-blur-md shadow-sm sticky top-0 z-50">
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
<div class="flex items-center justify-between h-16"><div class="flex items-center">
<a href="{{ url_for('index') }}" class="text-2xl font-bold fancy-text">CodeFest</a></div><div class="flex items-center space-x-2">
{% if 'admin_id' in session %}<a href="{{ url_for('admin_dashboard') }}" class="text-gray-600 dark:text-gray-300 hover:text-indigo-600 dark:hover:text-indigo-400 px-3 py-2 rounded-md text-sm font-medium">Dashboard</a>
<a href="{{ url_for('logout') }}" class="text-gray-600 dark:text-gray-300 hover:text-indigo-600 dark:hover:text-indigo-400 px-3 py-2 rounded-md text-sm font-medium">Logout</a>
{% elif 'student_email' in session %}<a href="{{ url_for('student_dashboard') }}" class="text-gray-600 dark:text-gray-300 hover:text-indigo-600 dark:hover:text-indigo-400 px-3 py-2 rounded-md text-sm font-medium">My Dashboard</a>
<a href="{{ url_for('logout') }}" class="text-gray-600 dark:text-gray-300 hover:text-indigo-600 dark:hover:text-indigo-400 px-3 py-2 rounded-md text-sm font-medium">Logout</a>
{% else %}<a href="{{ url_for('index') }}" class="text-gray-600 dark:text-gray-300 hover:text-indigo-600 dark:hover:text-indigo-400 px-3 py-2 rounded-md text-sm font-medium">Home</a>
<a href="{{ url_for('syllabus') }}" class="text-gray-600 dark:text-gray-300 hover:text-indigo-600 dark:hover:text-indigo-400 px-3 py-2 rounded-md text-sm font-medium">Syllabus</a>
<a href="{{ url_for('student_login') }}" class="text-gray-600 dark:text-gray-300 hover:text-indigo-600 dark:hover:text-indigo-400 px-3 py-2 rounded-md text-sm font-medium">Student Login</a>
<a href="{{ url_for('admin_login') }}" class="bg-indigo-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-indigo-700 transition-colors">Admin Login</a>
{% endif %}
<button id="theme-toggle" type="button" class="text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-4 focus:ring-gray-200 dark:focus:ring-gray-700 rounded-lg text-sm p-2.5">
    <svg id="theme-toggle-dark-icon" class="hidden w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"></path></svg>
    <svg id="theme-toggle-light-icon" class="hidden w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" fill-rule="evenodd" clip-rule="evenodd"></path></svg>
</button>
</div></div></div></nav><main>
{% with messages = get_flashed_messages(with_categories=true) %} {% if messages %}<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
{% for category, message in messages %}<div class="{% if category == 'success' %} bg-green-100 border-green-400 text-green-800 dark:bg-green-900/20 dark:border-green-600 dark:text-green-300 {% elif category == 'error' %} bg-red-100 border-red-400 text-red-800 dark:bg-red-900/20 dark:border-red-600 dark:text-red-300 {% else %} bg-blue-100 border-blue-400 text-blue-800 dark:bg-blue-900/20 dark:border-blue-600 dark:text-blue-300 {% endif %} border px-4 py-3 rounded-lg relative" role="alert">
<span class="block sm:inline">{{ message }}</span></div>{% endfor %}</div>{% endif %} {% endwith %}
{% block content %}{% endblock %}</main>
<footer class="bg-white dark:bg-gray-800 mt-12 py-6 border-t dark:border-gray-700"><div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-gray-500 dark:text-gray-400">
<p>This website is made by HrishabhxCode</p></div></footer>
<script>
    const themeToggleBtn = document.getElementById('theme-toggle');
    const themeToggleDarkIcon = document.getElementById('theme-toggle-dark-icon');
    const themeToggleLightIcon = document.getElementById('theme-toggle-light-icon');

    function setIconState() {
        if (document.documentElement.classList.contains('dark')) {
            themeToggleLightIcon.classList.remove('hidden');
            themeToggleDarkIcon.classList.add('hidden');
        } else {
            themeToggleDarkIcon.classList.remove('hidden');
            themeToggleLightIcon.classList.add('hidden');
        }
    }
    setIconState();
    themeToggleBtn.addEventListener('click', function() {
        document.documentElement.classList.toggle('dark');
        let theme = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
        localStorage.setItem('color-theme', theme);
        setIconState();
    });
</script>
</body></html>"""

HOMEPAGE_CONTENT = """
<div class="relative pt-16 pb-20 px-4 sm:px-6 lg:pt-24 lg:pb-28 lg:px-8">
    <div class="absolute inset-0"><div class="bg-white dark:bg-gray-900 h-1/3 sm:h-2/3"></div></div>
    <div class="relative max-w-7xl mx-auto">
        <div class="text-center">
            <h1 class="text-4xl tracking-tight font-extrabold text-gray-900 dark:text-white sm:text-5xl md:text-6xl">
                <span class="block">Welcome to</span>
                <span class="block fancy-text">CodeFest Contests</span>
            </h1>
            <p class="mt-3 max-w-md mx-auto text-base text-gray-500 dark:text-gray-400 sm:text-lg md:mt-5 md:text-xl md:max-w-3xl">
                Sharpen your skills and compete with the best. Find your next challenge below.
            </p>
            <div class="mt-5 max-w-md mx-auto sm:flex sm:justify-center md:mt-8">
                <div class="rounded-md shadow">
                    <a href="#contests" class="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 md:py-4 md:text-lg md:px-10">
                        View Contests
                    </a>
                </div>
                <div class="mt-3 rounded-md shadow sm:mt-0 sm:ml-3">
                    <a href="{{ url_for('public_results') }}" class="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-indigo-600 bg-white hover:bg-gray-50 md:py-4 md:text-lg md:px-10">
                        View Past Results
                    </a>
                </div>
            </div>
        </div>
        <div id="contests" class="mt-12 max-w-lg mx-auto grid gap-8 lg:grid-cols-3 lg:max-w-none">
            {% for contest in contests %}
            <div class="flex flex-col rounded-lg shadow-lg overflow-hidden transform hover:-translate-y-1 transition-transform duration-300">
                <div class="flex-1 bg-white dark:bg-gray-800 p-6 flex flex-col justify-between">
                    <div class="flex-1">
                        <p class="text-sm font-medium text-indigo-600 dark:text-indigo-400">Upcoming Contest</p>
                        <a href="{{ url_for('register', contest_id=contest.id) }}" class="block mt-2">
                            <p class="text-xl font-semibold text-gray-900 dark:text-white">{{ contest.name }}</p>
                        </a>
                    </div>
                    <div class="mt-6 flex items-center">
                        <div>
                            <p class="text-sm font-medium text-gray-900 dark:text-gray-200">Date: {{ contest.date.strftime('%B %d, %Y') }}</p>
                            <p class="text-sm text-gray-500 dark:text-gray-400">Time: {{ contest.test_time.strftime('%I:%M %p') if contest.test_time else 'Time TBD' }}</p>
                        </div>
                    </div>
                </div>
                <div class="p-4 bg-gray-50 dark:bg-gray-700"><a href="{{ url_for('register', contest_id=contest.id) }}" class="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-base font-medium text-white bg-indigo-600 hover:bg-indigo-700">Register Now</a></div>
            </div>
            {% else %}
            <div class="lg:col-span-3 bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 text-center">
                <h2 class="text-xl font-semibold text-gray-700 dark:text-gray-200">No active contests at the moment.</h2>
                <p class="text-gray-500 dark:text-gray-400 mt-2">Please check back later!</p>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
"""

SYLLABUS_CONTENT = """
<div class="max-w-4xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
    <h1 class="text-4xl font-extrabold text-center text-gray-900 dark:text-white mb-12">Contest Syllabus</h1>
    <div class="space-y-6">
        {% for contest in contests %}
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg overflow-hidden">
            <details class="group">
                <summary class="flex items-center justify-between p-6 cursor-pointer">
                    <div>
                        <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{{ contest.name }}</h2>
                        <p class="text-gray-500 dark:text-gray-400 mt-1">Date: {{ contest.date.strftime('%B %d, %Y') }}</p>
                    </div>
                    <span class="text-indigo-600 dark:text-indigo-400 group-open:rotate-90 transition-transform duration-300">&#9656;</span>
                </summary>
                <div class="p-6 border-t dark:border-gray-700">
                    <div class="prose dark:prose-invert max-w-none">
                        {{ contest.syllabus|safe if contest.syllabus else 'Syllabus not yet available.' }}
                    </div>
                </div>
            </details>
        </div>
        {% else %}
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 text-center">
            <h2 class="text-xl font-semibold text-gray-700 dark:text-gray-200">No syllabus available for active contests.</h2>
        </div>
        {% endfor %}
    </div>
</div>
"""

PUBLIC_RESULTS_CONTENT = """
<div class="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
    <h1 class="text-4xl font-extrabold text-center text-gray-900 dark:text-white mb-12">Published Contest Results</h1>
    <div class="space-y-12">
        {% for contest in contests %}
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg overflow-hidden">
            <div class="p-6">
                <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{{ contest.name }}</h2>
                <p class="text-gray-500 dark:text-gray-400 mt-1">Date: {{ contest.date.strftime('%B %d, %Y') }}</p>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead class="bg-gray-50 dark:bg-gray-700"><tr>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Rank</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Name</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">College</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Score</th>
                    </tr></thead>
                    <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                    {% for student in contest.students|sort(attribute='score', reverse=True) %}
                        {% if student.score is not none %}
                        <tr>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{{ loop.index }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">{{ student.name }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{{ student.college }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-bold text-gray-800 dark:text-white">{{ student.score }}</td>
                        </tr>
                        {% endif %}
                    {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% else %}
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 text-center">
            <h2 class="text-xl font-semibold text-gray-700 dark:text-gray-200">No published results available.</h2>
        </div>
        {% endfor %}
    </div>
</div>
"""

REGISTER_CONTENT = """
<div class="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-2xl w-full space-y-8">
        <div class="bg-white dark:bg-gray-800 p-10 rounded-xl shadow-lg">
            <h2 class="text-center text-3xl font-extrabold text-gray-900 dark:text-white">Register for {{ contest.name }}</h2>
            <p class="text-center text-gray-500 dark:text-gray-400 mt-2">Contest Date: {{ contest.date.strftime('%B %d, %Y') }} at {{ contest.test_time.strftime('%I:%M %p') if contest.test_time else 'Time TBD' }}</p>
            <div class="mt-6">
                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5"><div id="progress-bar" class="bg-indigo-600 h-2.5 rounded-full" style="width: 33%"></div></div>
                <div class="flex justify-between text-sm text-gray-500 dark:text-gray-400 mt-2">
                    <span id="step-1-text" class="font-bold text-indigo-600 dark:text-indigo-400">Personal Details</span><span id="step-2-text">Academic Info</span><span id="step-3-text">Confirm</span>
                </div>
            </div>
            <form id="registration-form" class="mt-8 space-y-6" action="{{ url_for('register', contest_id=contest.id) }}" method="POST">
                <div id="step-1" class="form-step form-step-active">
                    <h3 class="text-lg font-medium text-gray-800 dark:text-gray-200 mb-4">Step 1: Personal Details</h3>
                    <div class="space-y-4">
                        <div><label for="name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Full Name</label><input id="name" name="name" type="text" required class="mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"></div>
                        <div><label for="email" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Email Address</label><input id="email" name="email" type="email" autocomplete="email" required class="mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"></div>
                    </div>
                </div>
                <div id="step-2" class="form-step">
                    <h3 class="text-lg font-medium text-gray-800 dark:text-gray-200 mb-4">Step 2: Academic Information</h3>
                    <div class="space-y-4">
                        <div><label for="college" class="block text-sm font-medium text-gray-700 dark:text-gray-300">College/University Name</label><input id="college" name="college" type="text" value="NIT Nagaland" required class="mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"></div>
                        <div><label for="branch" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Branch</label><select id="branch" name="branch" required class="mt-1 block w-full px-3 py-2 border bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"><option value="" disabled selected>Select branch</option><option value="CSE">CSE</option><option value="ECE">ECE</option><option value="EIE">EIE</option><option value="ME">ME</option><option value="EEE">EEE</option><option value="Civil">Civil</option></select></div>
                        <div><label for="graduation_year" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Graduation Year</label><input id="graduation_year" name="graduation_year" type="number" min="2020" max="2030" required class="mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"></div>
                    </div>
                </div>
                <div id="step-3" class="form-step"><h3 class="text-lg font-medium text-gray-800 dark:text-gray-200 mb-4">Step 3: Confirm Your Details</h3><div id="confirmation-details" class="space-y-2 text-gray-700 dark:text-gray-300"></div></div>
                <div class="flex justify-between mt-8">
                    <button type="button" id="prev-btn" class="bg-gray-300 dark:bg-gray-600 text-gray-800 dark:text-gray-200 px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-400 dark:hover:bg-gray-500 disabled:opacity-50" disabled>Previous</button>
                    <button type="button" id="next-btn" class="bg-indigo-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-indigo-700">Next</button>
                    <button type="submit" id="submit-btn" class="hidden bg-green-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-green-700">Submit Registration</button>
                </div>
            </form>
        </div>
    </div>
</div>
<script>
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('registration-form'), steps = Array.from(document.querySelectorAll('.form-step')), prevBtn = document.getElementById('prev-btn'), nextBtn = document.getElementById('next-btn'), submitBtn = document.getElementById('submit-btn'), progressBar = document.getElementById('progress-bar'), stepTexts = [document.getElementById('step-1-text'), document.getElementById('step-2-text'), document.getElementById('step-3-text')]; let currentStep = 0;
    function updateButtons() { prevBtn.disabled = currentStep === 0; if (currentStep === steps.length - 1) { nextBtn.classList.add('hidden'); submitBtn.classList.remove('hidden'); } else { nextBtn.classList.remove('hidden'); submitBtn.classList.add('hidden'); } }
    function updateProgress() { const progress = ((currentStep + 1) / steps.length) * 100; progressBar.style.width = progress + '%'; stepTexts.forEach((text, index) => { text.classList.remove('font-bold', 'text-indigo-600', 'dark:text-indigo-400'); if (index === currentStep) { text.classList.add('font-bold', 'text-indigo-600', 'dark:text-indigo-400'); } }); }
    function showConfirmation() { const formData = new FormData(form); document.getElementById('confirmation-details').innerHTML = '<p><strong>Name:</strong> ' + formData.get('name') + '</p>' + '<p><strong>Email:</strong> ' + formData.get('email') + '</p>' + '<p><strong>College:</strong> ' + formData.get('college') + '</p>' + '<p><strong>Branch:</strong> ' + formData.get('branch') + '</p>' + '<p><strong>Graduation Year:</strong> ' + formData.get('graduation_year') + '</p>'; }
    function validateStep() { for (const field of steps[currentStep].querySelectorAll('input, select')) { if (!field.checkValidity()) { field.reportValidity(); return false; } } return true; }
    nextBtn.addEventListener('click', function () { if (!validateStep()) return; if (currentStep < steps.length - 1) { steps[currentStep].classList.remove('form-step-active'); currentStep++; steps[currentStep].classList.add('form-step-active'); if(currentStep === steps.length - 1) { showConfirmation(); } updateButtons(); updateProgress(); } });
    prevBtn.addEventListener('click', function () { if (currentStep > 0) { steps[currentStep].classList.remove('form-step-active'); currentStep--; steps[currentStep].classList.add('form-step-active'); updateButtons(); updateProgress(); } });
    updateButtons(); updateProgress();
});
</script>"""

ADMIN_LOGIN_CONTENT = """
<div class="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-4xl w-full space-y-8">
        <!-- Login Form -->
        <div class="bg-white dark:bg-gray-800 p-10 rounded-xl shadow-lg">
            <div>
                <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">Admin Panel Login</h2>
            </div>
            <form class="mt-8 space-y-6" action="{{ url_for('admin_login') }}" method="POST">
                <input type="hidden" name="action" value="login">
                <div class="rounded-md shadow-sm -space-y-px">
                    <div>
                        <label for="username" class="sr-only">Username</label>
                        <input id="username" name="username" type="text" required class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" placeholder="Username">
                    </div>
                    <div>
                        <label for="password" class="sr-only">Password</label>
                        <input id="password" name="password" type="password" required class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white rounded-b-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" placeholder="Password">
                    </div>
                </div>
                <div>
                    <button type="submit" class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">Sign in</button>
                </div>
            </form>
        </div>

        <!-- Registration Form -->
        <div class="bg-white dark:bg-gray-800 p-10 rounded-xl shadow-lg">
            <div>
                <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">Create New Admin Account</h2>
                {% if is_first_admin %}
                <div class="mt-2 text-center">
                    <p class="text-sm text-green-600 dark:text-green-400 font-medium">First Admin Setup</p>
                    <p class="text-xs text-gray-600 dark:text-gray-400">No admin accounts exist yet. Create the first admin account to get started.</p>
                </div>
                {% else %}
                <p class="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">Register a new admin user to access the admin panel</p>
                {% endif %}
                <div class="mt-3 text-center">
                    <div class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-300">
                        <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
                        </svg>
                        Security Code Required
                    </div>
                </div>
            </div>
            <form class="mt-8 space-y-6" action="{{ url_for('admin_login') }}" method="POST" id="registrationForm">
                <input type="hidden" name="action" value="register">
                <div class="rounded-md shadow-sm -space-y-px">
                    <div>
                        <label for="reg_username" class="sr-only">Username</label>
                        <input id="reg_username" name="reg_username" type="text" required class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" placeholder="Username">
                    </div>
                    <div>
                        <label for="reg_password" class="sr-only">Password</label>
                        <input id="reg_password" name="reg_password" type="password" required class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" placeholder="Password">
                    </div>
                    <div>
                        <label for="reg_confirm_password" class="sr-only">Confirm Password</label>
                        <input id="reg_confirm_password" name="reg_confirm_password" type="password" required class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" placeholder="Confirm Password">
                    </div>
                    <div>
                        <label for="security_code" class="sr-only">Security Code</label>
                        <input id="security_code" name="security_code" type="text" required class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" placeholder="Security Code (Required)">
                    </div>
                </div>
                <div id="passwordMatch" class="text-sm text-red-600 dark:text-red-400 hidden">Passwords do not match</div>
                <div class="text-xs text-gray-600 dark:text-gray-400 text-center">
                    <p>⚠️ Admin registration is restricted. You must have the security code to create an admin account.</p>
                </div>
                <div>
                    <button type="submit" class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500">Create Admin Account</button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    const passwordInput = document.getElementById('reg_password');
    const confirmPasswordInput = document.getElementById('reg_confirm_password');
    const passwordMatchDiv = document.getElementById('passwordMatch');
    const registrationForm = document.getElementById('registrationForm');
    
    function checkPasswordMatch() {
        if (confirmPasswordInput.value && passwordInput.value !== confirmPasswordInput.value) {
            passwordMatchDiv.classList.remove('hidden');
            confirmPasswordInput.classList.add('border-red-500');
            confirmPasswordInput.classList.remove('border-gray-300', 'dark:border-gray-600');
        } else {
            passwordMatchDiv.classList.add('hidden');
            confirmPasswordInput.classList.remove('border-red-500');
            confirmPasswordInput.classList.add('border-gray-300', 'dark:border-gray-600');
        }
    }
    
    passwordInput.addEventListener('input', checkPasswordMatch);
    confirmPasswordInput.addEventListener('input', checkPasswordMatch);
    
    registrationForm.addEventListener('submit', function(e) {
        if (passwordInput.value !== confirmPasswordInput.value) {
            e.preventDefault();
            passwordMatchDiv.classList.remove('hidden');
            confirmPasswordInput.classList.add('border-red-500');
            confirmPasswordInput.classList.remove('border-gray-300', 'dark:border-gray-600');
            return false;
        }
    });
});
</script>"""

ADMIN_LAYOUT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Admin Panel</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script>
        if (localStorage.getItem('color-theme') === 'dark' || (!('color-theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark')
        }
    </script>
    <style>
        body { font-family: 'Poppins', sans-serif; }
        .admin-sidebar { transition: transform 0.3s ease-in-out; }
        .admin-content { transition: margin-left 0.3s ease-in-out; }
        @media (max-width: 768px) {
            .admin-sidebar { transform: translateX(-100%); }
            .admin-sidebar.open { transform: translateX(0); }
            .admin-content { margin-left: 0; }
        }
        .nav-item { transition: all 0.2s ease-in-out; }
        .nav-item:hover { transform: translateX(4px); }
        .nav-item.active { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .nav-item.active:hover { transform: none; }
        
        /* Fix sidebar positioning */
        .admin-sidebar {
            position: fixed;
            top: 0;
            left: 0;
            height: 100vh;
            z-index: 40;
        }
        
        .admin-content {
            margin-left: 18rem; /* 72 * 0.25rem = 18rem */
        }
        
        @media (max-width: 1024px) {
            .admin-content {
                margin-left: 0;
            }
        }
    </style>
</head>
<body class="bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-200 transition-colors duration-300">
    <!-- Mobile Menu Button -->
    <div class="lg:hidden fixed top-4 left-4 z-50">
        <button id="mobile-menu-btn" class="bg-gray-800 text-white p-2 rounded-md shadow-lg hover:bg-gray-700 transition-colors">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
            </svg>
        </button>
    </div>

    <!-- Admin Sidebar -->
    <div id="admin-sidebar" class="admin-sidebar w-72 bg-gradient-to-b from-gray-800 to-gray-900 text-white shadow-2xl">
        <!-- Sidebar Header -->
        <div class="flex items-center justify-between px-6 py-6 border-b border-gray-700/50">
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                    <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
                    </svg>
                </div>
                <div>
                    <h2 class="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">Admin Panel</h2>
                    <p class="text-xs text-gray-400">Contest Management</p>
                </div>
            </div>
            <button id="close-sidebar" class="lg:hidden text-gray-400 hover:text-white transition-colors">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        </div>
        
        <!-- Navigation Menu -->
        <nav class="flex-1 px-4 py-6 space-y-2">
            <!-- Main Navigation Section -->
            <div class="mb-6">
                <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 mb-3">Main</h3>
                <div class="space-y-1">
                    <a href="{{ url_for('admin_dashboard') }}" class="nav-item flex items-center px-4 py-3 rounded-lg transition-all duration-200 {% if request.endpoint == 'admin_dashboard' %}active text-white{% else %}text-gray-300 hover:text-white hover:bg-gray-700/50{% endif %}">
                        <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z"></path>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5a2 2 0 012-2h4a2 2 0 012 2v6H8V5z"></path>
                        </svg>
                        <span class="font-medium">Dashboard</span>
                    </a>
                </div>
            </div>

            <!-- Contest Management Section -->
            <div class="mb-6">
                <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 mb-3">Contests</h3>
                <div class="space-y-1">
                    <a href="{{ url_for('admin_manage_contests') }}" class="nav-item flex items-center px-4 py-3 rounded-lg transition-all duration-200 {% if 'contest' in request.endpoint and 'past' not in request.endpoint and 'edit' not in request.endpoint %}active text-white{% else %}text-gray-300 hover:text-white hover:bg-gray-700/50{% endif %}">
                        <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                        </svg>
                        <span class="font-medium">Manage Contests</span>
                    </a>
                    <a href="{{ url_for('admin_past_contests') }}" class="nav-item flex items-center px-4 py-3 rounded-lg transition-all duration-200 {% if 'past_contest' in request.endpoint %}active text-white{% else %}text-gray-300 hover:text-white hover:bg-gray-700/50{% endif %}">
                        <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        <span class="font-medium">Past Contests</span>
                    </a>
                </div>
            </div>

            <!-- Student Management Section -->
            <div class="mb-6">
                <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 mb-3">Students</h3>
                <div class="space-y-1">
                    <a href="{{ url_for('admin_manual_registration') }}" class="nav-item flex items-center px-4 py-3 rounded-lg transition-all duration-200 {% if request.endpoint == 'admin_manual_registration' %}active text-white{% else %}text-gray-300 hover:text-white hover:bg-gray-700/50{% endif %}">
                        <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"></path>
                        </svg>
                        <span class="font-medium">Add Student</span>
                    </a>
                </div>
            </div>

            <!-- Settings Section -->
            <div class="mb-6">
                <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 mb-3">Settings</h3>
                <div class="space-y-1">
                    <a href="{{ url_for('admin_settings') }}" class="nav-item flex items-center px-4 py-3 rounded-lg transition-all duration-200 {% if request.endpoint == 'admin_settings' %}active text-white{% else %}text-gray-300 hover:text-white hover:bg-gray-700/50{% endif %}">
                        <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        </svg>
                        <span class="font-medium">Global Settings</span>
                    </a>
                    <a href="{{ url_for('admin_manage_admins') }}" class="nav-item flex items-center px-4 py-3 rounded-lg transition-all duration-200 {% if request.endpoint == 'admin_manage_admins' %}active text-white{% else %}text-gray-300 hover:text-white hover:bg-gray-700/50{% endif %}">
                        <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"></path>
                        </svg>
                        <span class="font-medium">Manage Admins</span>
                    </a>
                </div>
            </div>
        </nav>
        
        <!-- Sidebar Footer -->
        <div class="px-4 py-4 border-t border-gray-700/50">
            <a href="{{ url_for('logout') }}" class="nav-item flex items-center px-4 py-3 rounded-lg transition-all duration-200 text-red-400 hover:text-red-300 hover:bg-red-500/10">
                <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
                </svg>
                <span class="font-medium">Logout</span>
            </a>
        </div>
    </div>

    <!-- Main Content -->
    <div class="admin-content lg:ml-72 min-h-screen">
        <!-- Top Bar -->
        <div class="bg-white dark:bg-gray-800 shadow-sm border-b dark:border-gray-700">
            <div class="flex items-center justify-between px-6 py-4">
                <div class="flex items-center">
                    <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{{ title }}</h1>
                </div>
                <div class="flex items-center space-x-4">
                    <button id="theme-toggle" type="button" class="text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-4 focus:ring-gray-200 dark:focus:ring-gray-700 rounded-lg text-sm p-2.5 transition-colors">
                        <svg id="theme-toggle-dark-icon" class="hidden w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                            <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"></path>
                        </svg>
                        <svg id="theme-toggle-light-icon" class="hidden w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                            <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" fill-rule="evenodd" clip-rule="evenodd"></path>
                        </svg>
                    </button>
                </div>
            </div>
        </div>

        <!-- Flash Messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="px-6 py-4">
                    {% for category, message in messages %}
                        <div class="{% if category == 'success' %}bg-green-100 border-green-400 text-green-800 dark:bg-green-900/20 dark:border-green-600 dark:text-green-300{% elif category == 'error' %}bg-red-100 border-red-400 text-red-800 dark:bg-red-900/20 dark:border-red-600 dark:text-red-300{% else %}bg-blue-100 border-blue-400 text-blue-800 dark:bg-blue-900/20 dark:border-blue-600 dark:text-blue-300{% endif %} border px-4 py-3 rounded-lg relative mb-4 shadow-sm" role="alert">
                            <span class="block sm:inline">{{ message }}</span>
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <!-- Page Content -->
        <div class="p-6">
            {% block admin_content %}{% endblock %}
        </div>
    </div>

    <script>
        // Mobile menu functionality
        const mobileMenuBtn = document.getElementById('mobile-menu-btn');
        const closeSidebarBtn = document.getElementById('close-sidebar');
        const adminSidebar = document.getElementById('admin-sidebar');
        const adminContent = document.querySelector('.admin-content');

        mobileMenuBtn.addEventListener('click', () => {
            adminSidebar.classList.add('open');
        });

        closeSidebarBtn.addEventListener('click', () => {
            adminSidebar.classList.remove('open');
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 && 
                !adminSidebar.contains(e.target) && 
                !mobileMenuBtn.contains(e.target)) {
                adminSidebar.classList.remove('open');
            }
        });

        // Theme toggle functionality
        const themeToggleBtn = document.getElementById('theme-toggle');
        const themeToggleDarkIcon = document.getElementById('theme-toggle-dark-icon');
        const themeToggleLightIcon = document.getElementById('theme-toggle-light-icon');

        function setIconState() {
            if (document.documentElement.classList.contains('dark')) {
                themeToggleLightIcon.classList.remove('hidden');
                themeToggleDarkIcon.classList.add('hidden');
            } else {
                themeToggleDarkIcon.classList.remove('hidden');
                themeToggleLightIcon.classList.add('hidden');
            }
        }

        setIconState();

        themeToggleBtn.addEventListener('click', function() {
            document.documentElement.classList.toggle('dark');
            let theme = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
            localStorage.setItem('color-theme', theme);
            setIconState();
        });
    </script>
</body>
</html>
"""

ADMIN_DASHBOARD_CONTENT = """
<div class="max-w-7xl mx-auto">
    <div class="flex justify-between items-center mb-6"><h1 class="text-3xl font-bold text-gray-900 dark:text-white">Dashboard</h1></div>
    
    <!-- Security Information Card -->
    <div class="bg-gradient-to-r from-red-50 to-orange-50 dark:from-red-900/20 dark:to-orange-900/20 border border-red-200 dark:border-red-800 p-6 rounded-lg shadow-lg mb-8">
        <div class="flex items-center justify-between">
            <div class="flex items-center">
                <svg class="w-6 h-6 text-red-600 dark:text-red-400 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
                </svg>
                <h2 class="text-xl font-semibold text-red-800 dark:text-red-200">Security Information</h2>
            </div>
            <a href="{{ url_for('admin_settings') }}" class="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200 text-sm font-medium">View Details →</a>
        </div>
        
        <div class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="bg-white dark:bg-gray-700 p-4 rounded-lg border border-red-200 dark:border-red-600">
                <div class="text-center">
                    <div class="text-2xl font-bold text-red-600 dark:text-red-400">HRISHABHADMIN2025</div>
                    <div class="text-xs text-red-600 dark:text-red-400 mt-1">Registration Code</div>
                </div>
            </div>
            <div class="bg-white dark:bg-gray-700 p-4 rounded-lg border border-red-200 dark:border-red-600">
                <div class="text-center">
                    <div class="text-2xl font-bold text-red-600 dark:text-red-400">5</div>
                    <div class="text-xs text-red-600 dark:text-red-400 mt-1">Max Failed Attempts</div>
                </div>
            </div>
            <div class="bg-white dark:bg-gray-700 p-4 rounded-lg border border-red-200 dark:border-red-600">
                <div class="text-center">
                    <div class="text-2xl font-bold text-red-600 dark:text-red-400">5 min</div>
                    <div class="text-xs text-red-600 dark:text-red-400 mt-1">Lockout Duration</div>
                </div>
            </div>
        </div>
        
        <div class="mt-4 text-center">
            <p class="text-sm text-red-600 dark:text-red-400">
                ⚠️ Admin registration is restricted. Only users with the security code can create admin accounts.
            </p>
        </div>
    </div>
    
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg"><h3 class="text-gray-500 dark:text-gray-400 text-sm font-medium">Total Applicants</h3><p class="text-3xl font-semibold text-gray-900 dark:text-white">{{ stats.total }}</p></div>
        <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg"><h3 class="text-gray-500 dark:text-gray-400 text-sm font-medium">Accepted</h3><p class="text-3xl font-semibold text-green-600">{{ stats.accepted }}</p></div>
        <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg"><h3 class="text-gray-500 dark:text-gray-400 text-sm font-medium">Pending</h3><p class="text-3xl font-semibold text-yellow-600">{{ stats.pending }}</p></div>
        <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg"><h3 class="text-gray-500 dark:text-gray-400 text-sm font-medium">Denied</h3><p class="text-3xl font-semibold text-red-600">{{ stats.denied }}</p></div>
    </div>
    <div class="bg-white dark:bg-gray-800 shadow-xl rounded-lg overflow-hidden">
        <form id="main-form" method="GET" action="{{ url_for('admin_dashboard') }}">
            <div class="px-6 py-4 border-b dark:border-gray-700">
                <h2 class="text-xl font-semibold text-gray-800 dark:text-white">Manage Applications</h2>
                <div class="mt-4 grid grid-cols-1 md:grid-cols-5 gap-4">
                    <select name="contest_id" onchange="this.form.submit()" class="md:col-span-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                        <option value="">All Contests</option>
                        {% for contest in all_contests %}<option value="{{ contest.id }}" {% if request.args.get('contest_id')|int == contest.id %}selected{% endif %}>{{ contest.name }}</option>{% endfor %}
                    </select>
                    <input type="text" name="search" placeholder="Search by Name/Email..." value="{{ request.args.get('search', '') }}" onchange="this.form.submit()" class="md:col-span-2 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                    <select name="branch" onchange="this.form.submit()" class="block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                        <option value="">All Branches</option>
                        {% for branch in branches %}<option value="{{ branch }}" {% if request.args.get('branch') == branch %}selected{% endif %}>{{ branch }}</option>{% endfor %}
                    </select>
                    <select name="status" onchange="this.form.submit()" class="block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                        <option value="">All Statuses</option><option value="Pending" {% if request.args.get('status') == 'Pending' %}selected{% endif %}>Pending</option><option value="Accepted" {% if request.args.get('status') == 'Accepted' %}selected{% endif %}>Accepted</option><option value="Denied" {% if request.args.get('status') == 'Denied' %}selected{% endif %}>Denied</option>
                    </select>
                </div>
                <div class="mt-4 flex justify-between items-center">
                    <div><a href="{{ url_for('send_test_links') }}" class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700">Send Test Links to Verified Candidates</a></div>
                    <div class="flex space-x-2"><a href="{{ url_for('admin_export_csv') }}" class="bg-teal-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-teal-700">Export CSV</a><a href="{{ url_for('admin_export_pdf') }}" class="bg-green-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-green-700">Export PDF</a></div>
                </div>
            </div>
            <div class="overflow-x-auto"><table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700"><thead class="bg-gray-50 dark:bg-gray-700"><tr>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Applicant</th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Details</th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Status</th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Actions</th>
            </tr></thead><tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {% for student in students %}<tr>
                <td class="px-6 py-4 whitespace-nowrap"><div class="text-sm font-medium text-gray-900 dark:text-white">{{ student.name }}</div><div class="text-xs text-gray-500 dark:text-gray-400">{{ student.email }}</div><div class="text-xs text-indigo-500 dark:text-indigo-400 font-semibold">{{ student.contest.name }}</div></td>
                <td class="px-6 py-4 whitespace-nowrap"><div class="text-sm text-gray-900 dark:text-white">{{ student.college }}</div><div class="text-xs text-gray-500 dark:text-gray-400">{{ student.branch }} - {{student.graduation_year}}</div></td>
                <td class="px-6 py-4 whitespace-nowrap text-sm"><span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {% if student.status == 'Accepted' %} bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-300 {% elif student.status == 'Denied' %} bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-300 {% else %} bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-300 {% endif %}">{{ student.status }}</span></td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    {% if student.status == 'Pending' %}<a href="{{ url_for('update_status', student_id=student.id, status='Accepted') }}" class="inline-flex items-center px-2.5 py-1.5 border border-transparent text-xs font-medium rounded shadow-sm text-white bg-green-600 hover:bg-green-700">Accept</a>
                    <a href="{{ url_for('update_status', student_id=student.id, status='Denied') }}" class="inline-flex items-center px-2.5 py-1.5 border border-transparent text-xs font-medium rounded shadow-sm text-white bg-red-600 hover:bg-red-700 ml-2">Deny</a>
                    {% elif student.status == 'Accepted' %}<form action="{{ url_for('update_test_info', student_id=student.id) }}" method="post" class="flex items-center space-x-2"><input type="url" name="test_link" id="test-link-{{ student.id }}" placeholder="HackerRank Link" value="{{ student.test_link or '' }}" class="w-32 px-2 py-1 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md text-xs"><input type="number" name="score" placeholder="Score" value="{{ student.score or '' }}" class="w-20 px-2 py-1 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md text-xs"><button type="submit" class="px-2 py-1 bg-indigo-500 text-white rounded-md hover:bg-indigo-600 text-xs">Save</button></form>
                    {% else %}<span class="text-gray-400 dark:text-gray-500 text-sm">No action</span>{% endif %}
                    <a href="{{ url_for('admin_edit_student', student_id=student.id) }}" class="text-indigo-600 hover:text-indigo-900 ml-4">Edit</a>
                    <form action="{{ url_for('admin_delete_student', student_id=student.id) }}" method="POST" class="inline-block ml-2"><button type="submit" class="text-red-600 hover:text-red-900" onclick="return confirm('Are you sure you want to delete this registration permanently?')">Delete</button></form>
                </td>
            </tr>{% else %}<tr><td colspan="4" class="px-6 py-4 text-center text-gray-500 dark:text-gray-400">No students match the current filters.</td></tr>{% endfor %}
            </tbody></table></div></form></div></div>
"""

ADMIN_MANAGE_CONTESTS_CONTENT = """
<div class="flex justify-between items-center mb-6"><h1 class="text-3xl font-bold text-gray-900 dark:text-white">Manage Contests</h1></div>
<div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
    <div class="lg:col-span-1"><div class="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg">
        <h2 class="text-xl font-semibold mb-4 dark:text-white">Add New Contest</h2>
        <form action="{{ url_for('admin_manage_contests') }}" method="POST" class="space-y-4">
            <div><label for="name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Contest Name</label><input type="text" name="name" id="name" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
            <div><label for="date" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Contest Date</label><input type="date" name="date" id="date" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
            <div><label for="test_time" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Test Time</label><input type="time" name="test_time" id="test_time" class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
            <div><label for="syllabus" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Syllabus (HTML allowed)</label><textarea name="syllabus" id="syllabus" rows="5" class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></textarea></div>
            <div class="flex justify-end"><button type="submit" class="bg-indigo-600 text-white px-6 py-2 rounded-md font-medium hover:bg-indigo-700">Add Contest</button></div>
        </form>
    </div></div>
    <div class="lg:col-span-2"><div class="bg-white dark:bg-gray-800 shadow-xl rounded-lg overflow-hidden">
        <div class="overflow-x-auto"><table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700"><thead class="bg-gray-50 dark:bg-gray-700"><tr>
            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Name</th>
            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Date & Time</th>
            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Status</th>
            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Actions</th>
        </tr></thead><tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
        {% for contest in contests %}<tr>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{{ contest.name }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{{ contest.date.strftime('%Y-%m-%d') }} at {{ contest.test_time.strftime('%I:%M %p') if contest.test_time else 'N/A' }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                {% if contest.is_active %}<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-300">Active</span>
                {% else %}<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800 dark:bg-gray-600 dark:text-gray-200">Inactive</span>{% endif %}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <a href="{{ url_for('admin_edit_contest', contest_id=contest.id) }}" class="text-indigo-600 hover:text-indigo-900 mr-3">Edit</a>
                <a href="{{ url_for('admin_toggle_contest', contest_id=contest.id) }}" class="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white mr-3">Toggle Active</a>
                <a href="{{ url_for('admin_delete_contest', contest_id=contest.id) }}" onclick="return confirm('Are you sure? This will delete the contest and all associated registrations.')" class="text-red-600 hover:text-red-900">Delete</a>
            </td>
        </tr>{% else %}<tr><td colspan="4" class="px-6 py-4 text-center text-gray-500 dark:text-gray-400">No contests created yet.</td></tr>{% endfor %}
        </tbody></table></div>
    </div></div>
</div>
"""

ADMIN_EDIT_CONTEST_CONTENT = """
<h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-6">Edit Contest</h1>
<div class="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg max-w-2xl mx-auto">
    <form action="{{ url_for('admin_edit_contest', contest_id=contest.id) }}" method="POST" class="space-y-4">
        <div><label for="name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Contest Name</label><input type="text" name="name" id="name" value="{{ contest.name }}" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div><label for="date" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Contest Date</label><input type="date" name="date" id="date" value="{{ contest.date.strftime('%Y-%m-%d') }}" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div><label for="test_time" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Test Time</label><input type="time" name="test_time" id="test_time" value="{{ contest.test_time.strftime('%H:%M') if contest.test_time else '' }}" class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div><label for="syllabus" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Syllabus (HTML allowed)</label><textarea name="syllabus" id="syllabus" rows="10" class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500">{{ contest.syllabus or '' }}</textarea></div>
        <div class="flex justify-end"><button type="submit" class="bg-green-600 text-white px-6 py-2 rounded-md font-medium hover:bg-green-700">Save Changes</button></div>
    </form>
</div>
"""

ADMIN_PAST_CONTESTS_CONTENT = """
<div class="flex justify-between items-center mb-6"><h1 class="text-3xl font-bold text-gray-900 dark:text-white">Past Contests</h1></div>
<div class="bg-white dark:bg-gray-800 shadow-xl rounded-lg overflow-hidden">
    <div class="overflow-x-auto"><table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700"><thead class="bg-gray-50 dark:bg-gray-700"><tr>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Contest Name</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Date</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Participants</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Results</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Actions</th>
    </tr></thead><tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
    {% for contest in contests %}<tr>
        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{{ contest.name }}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{{ contest.date.strftime('%Y-%m-%d') }}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{{ contest.students|length }}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm">
            {% if contest.publish_results %}<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-300">Published</span>
            {% else %}<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800 dark:bg-gray-600 dark:text-gray-200">Not Published</span>{% endif %}
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
            <a href="{{ url_for('admin_view_contest_results', contest_id=contest.id) }}" class="text-indigo-600 hover:text-indigo-900 mr-3">View/Edit Results</a>
            <a href="{{ url_for('admin_toggle_publish', contest_id=contest.id) }}" class="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white">
                {{ 'Unpublish' if contest.publish_results else 'Publish' }}
            </a>
        </td>
    </tr>{% else %}<tr><td colspan="5" class="px-6 py-4 text-center text-gray-500 dark:text-gray-400">No past contests found.</td></tr>{% endfor %}
    </tbody></table></div>
</div>
"""

ADMIN_VIEW_RESULTS_CONTENT = """
<div class="flex justify-between items-center mb-6"><h1 class="text-3xl font-bold text-gray-900 dark:text-white">Results for {{ contest.name }}</h1></div>
<div class="bg-white dark:bg-gray-800 shadow-xl rounded-lg overflow-hidden">
    <div class="p-6 border-b dark:border-gray-700"><h2 class="text-xl font-semibold text-gray-800 dark:text-white">Manual Score Entry</h2></div>
    <div class="overflow-x-auto"><table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700"><thead class="bg-gray-50 dark:bg-gray-700"><tr>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Name</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Email</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Current Score</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Update Score</th>
    </tr></thead><tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
    {% for student in students %}<tr>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">{{ student.name }}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{{ student.email }}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm font-bold text-gray-800 dark:text-white">{{ student.score if student.score is not none else 'N/A' }}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
            <form action="{{ url_for('update_test_info', student_id=student.id) }}" method="post" class="flex items-center space-x-2">
                <input type="number" name="score" placeholder="New Score" class="w-24 px-2 py-1 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md text-xs">
                <button type="submit" class="px-2 py-1 bg-indigo-500 text-white rounded-md hover:bg-indigo-600 text-xs">Save</button>
            </form>
        </td>
    </tr>{% else %}<tr><td colspan="4" class="px-6 py-4 text-center text-gray-500 dark:text-gray-400">No participants found for this contest.</td></tr>{% endfor %}
    </tbody></table></div>
</div>
"""

ADMIN_REGISTER_ADMIN_CONTENT = """
<h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-6">Register New Admin</h1>
<div class="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg max-w-lg mx-auto">
    <form action="{{ url_for('admin_register_admin') }}" method="POST" class="space-y-6">
        <div><label for="username" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Username</label>
        <input type="text" name="username" id="username" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div><label for="password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Password</label>
        <input type="password" name="password" id="password" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div class="flex justify-end"><button type="submit" class="bg-indigo-600 text-white px-6 py-2 rounded-md font-medium hover:bg-indigo-700">Create Admin</button></div>
    </form>
</div>
"""

ADMIN_SETTINGS_CONTENT = """
<h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-6">Global Settings</h1>

<!-- Security Information Section -->
<div class="bg-gradient-to-r from-red-50 to-orange-50 dark:from-red-900/20 dark:to-orange-900/20 border border-red-200 dark:border-red-800 p-6 rounded-lg shadow-lg max-w-2xl mx-auto mb-8">
    <div class="flex items-center mb-4">
        <svg class="w-6 h-6 text-red-600 dark:text-red-400 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
        </svg>
        <h2 class="text-xl font-semibold text-red-800 dark:text-red-200">Security Information</h2>
    </div>
    
    <div class="space-y-4">
        <div>
            <label class="block text-sm font-medium text-red-700 dark:text-red-300 mb-2">Admin Registration Security Code</label>
            <div class="flex items-center space-x-2">
                <input type="password" id="security-code-input" value="HRISHABHADMIN2025" readonly 
                       class="flex-1 px-3 py-2 bg-white dark:bg-gray-700 border border-red-300 dark:border-red-600 rounded-md text-sm font-mono text-red-800 dark:text-red-200 cursor-text">
                <button type="button" id="toggle-mask" onclick="toggleMask()" 
                        class="px-3 py-2 bg-gray-600 text-white text-sm rounded-md hover:bg-gray-700 transition-colors">
                    Show
                </button>
                <button type="button" onclick="copyToClipboard(document.getElementById('security-code-input'))" 
                        class="px-3 py-2 bg-red-600 text-white text-sm rounded-md hover:bg-red-700 transition-colors">
                    Copy
                </button>
            </div>
            <p class="mt-2 text-xs text-red-600 dark:text-red-400">
                ⚠️ This code is required to create new admin accounts. Keep it secure and share only with authorized personnel.
            </p>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-red-200 dark:border-red-700">
            <div class="text-center">
                <div class="text-2xl font-bold text-red-600 dark:text-red-400">5</div>
                <div class="text-xs text-red-600 dark:text-red-400">Max Failed Attempts</div>
            </div>
            <div class="text-center">
                <div class="text-2xl font-bold text-red-600 dark:text-red-400">5 min</div>
                <div class="text-xs text-red-600 dark:text-red-400">Lockout Duration</div>
            </div>
        </div>
    </div>
</div>

<!-- Global Settings Form -->
<div class="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg max-w-2xl mx-auto">
    <form action="{{ url_for('admin_settings') }}" method="POST" class="space-y-6">
        <div>
            <label for="global_test_link" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Global HackerRank Test Link</label>
            <input type="url" name="global_test_link" id="global_test_link" value="{{ global_test_link or '' }}" required 
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500">
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">This link will be assigned to all accepted students when you use the "Assign & Email All" feature.</p>
        </div>
        <div class="flex justify-end">
            <button type="submit" class="bg-green-600 text-white px-6 py-2 rounded-md font-medium hover:bg-green-700">Save Settings</button>
        </div>
    </form>
</div>

<script>
function copyToClipboard(inputElement) {
    inputElement.select();
    inputElement.setSelectionRange(0, 99999); // For mobile devices
    document.execCommand('copy');
    
    // Show feedback
    const button = inputElement.nextElementSibling;
    const originalText = button.textContent;
    button.textContent = 'Copied!';
    button.classList.add('bg-green-600', 'hover:bg-green-700');
    button.classList.remove('bg-red-600', 'hover:bg-red-700');
    
    setTimeout(() => {
        button.textContent = originalText;
        button.classList.remove('bg-green-600', 'hover:bg-green-700');
        button.classList.add('bg-red-600', 'hover:bg-red-700');
    }, 2000);
}

function toggleMask() {
    const input = document.getElementById('security-code-input');
    const button = document.getElementById('toggle-mask');
    
    if (input.type === 'password') {
        input.type = 'text';
        button.textContent = 'Hide';
        button.classList.remove('bg-gray-600', 'hover:bg-gray-700');
        button.classList.add('bg-orange-600', 'hover:bg-orange-700');
    } else {
        input.type = 'password';
        button.textContent = 'Show';
        button.classList.remove('bg-orange-600', 'hover:bg-orange-700');
        button.classList.add('bg-gray-600', 'hover:bg-gray-700');
    }
}
</script>
"""

ADMIN_EMAIL_SETTINGS_CONTENT = """
<h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-6">Email Settings</h1>
<div class="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg max-w-2xl mx-auto">
    <form action="{{ url_for('admin_email_settings') }}" method="POST" class="space-y-6">
        <div>
            <label for="mail_username" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Email Username</label>
            <input type="email" name="mail_username" id="mail_username" value="{{ mail_username or '' }}" required 
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500">
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">The email address that will be used to send emails to students.</p>
        </div>
        <div>
            <label for="mail_password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Email Password</label>
            <input type="password" name="mail_password" id="mail_password" value="{{ mail_password or '' }}" required 
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500">
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">The password for the email account (app password for Gmail).</p>
        </div>
        <div class="flex justify-end">
            <button type="submit" class="bg-blue-600 text-white px-6 py-2 rounded-md font-medium hover:bg-blue-700">Save Email Settings</button>
        </div>
    </form>
</div>
"""

ADMIN_MANUAL_REG_CONTENT = """
<h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-6">Manual Student Registration</h1>
<div class="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg max-w-2xl mx-auto">
    <form action="{{ url_for('admin_manual_registration') }}" method="POST" class="space-y-6">
        <div><label for="contest_id" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Contest</label>
        <select name="contest_id" id="contest_id" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500">
            {% for contest in contests %}<option value="{{ contest.id }}">{{ contest.name }}</option>{% endfor %}
        </select></div>
        <div><label for="name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Full Name</label><input type="text" name="name" id="name" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div><label for="email" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Email</label><input type="email" name="email" id="email" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div><label for="college" class="block text-sm font-medium text-gray-700 dark:text-gray-300">College</label><input type="text" name="college" id="college" value="NIT Nagaland" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div><label for="branch" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Branch</label><select name="branch" id="branch" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"><option value="CSE">CSE</option><option value="ECE">ECE</option><option value="EIE">EIE</option><option value="ME">ME</option><option value="EEE">EEE</option><option value="Civil">Civil</option></select></div>
        <div><label for="graduation_year" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Graduation Year</label><input type="number" name="graduation_year" id="graduation_year" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div class="flex justify-end"><button type="submit" class="bg-indigo-600 text-white px-6 py-2 rounded-md font-medium hover:bg-indigo-700">Register Student</button></div>
    </form>
</div>
"""

ADMIN_EDIT_STUDENT_CONTENT = """
<h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-6">Edit Registration for {{ student.name }}</h1>
<div class="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg max-w-2xl mx-auto">
    <form action="{{ url_for('admin_edit_student', student_id=student.id) }}" method="POST" class="space-y-6">
        <div class="border-b dark:border-gray-700 pb-4">
            <h3 class="text-lg font-medium text-gray-800 dark:text-gray-200">Contest: {{ student.contest.name }}</h3>
        </div>
        <div><label for="name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Full Name</label><input type="text" name="name" id="name" value="{{ student.name }}" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div><label for="email" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Email</label><input type="email" name="email" id="email" value="{{ student.email }}" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div><label for="college" class="block text-sm font-medium text-gray-700 dark:text-gray-300">College</label><input type="text" name="college" id="college" value="{{ student.college or '' }}" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div><label for="branch" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Branch</label><select name="branch" id="branch" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500">{% for b in branches %}<option value="{{ b }}" {% if student.branch == b %}selected{% endif %}>{{ b }}</option>{% endfor %}</select></div>
        <div><label for="graduation_year" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Graduation Year</label><input type="number" name="graduation_year" id="graduation_year" value="{{ student.graduation_year or '' }}" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></div>
        <div><label for="status" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Status</label><select name="status" id="status" required class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"><option value="Pending" {% if student.status == 'Pending' %}selected{% endif %}>Pending</option><option value="Accepted" {% if student.status == 'Accepted' %}selected{% endif %}>Accepted</option><option value="Denied" {% if student.status == 'Denied' %}selected{% endif %}>Denied</option></select></div>
        <div class="flex justify-end space-x-4"><a href="{{ url_for('admin_dashboard') }}" class="bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-200 px-6 py-2 rounded-md font-medium hover:bg-gray-300 dark:hover:bg-gray-500">Cancel</a><button type="submit" class="bg-green-600 text-white px-6 py-2 rounded-md font-medium hover:bg-green-700">Save Changes</button></div>
    </form>
</div>
{% if past_performance|length > 0 %}
<div class="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg max-w-2xl mx-auto mt-8">
    <h2 class="text-xl font-semibold text-gray-800 dark:text-white mb-4">Past Performance for {{ student.name }}</h2>
    <div class="overflow-x-auto"><table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700"><thead class="bg-gray-50 dark:bg-gray-700"><tr>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Contest</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Date</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Score</th>
    </tr></thead><tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
    {% for reg in past_performance %}<tr>
        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{{ reg.contest.name }}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{{ reg.contest.date.strftime('%Y-%m-%d') }}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm font-bold text-gray-800 dark:text-white">{{ reg.score if reg.score is not none else 'N/A' }}</td>
    </tr>{% endfor %}
    </tbody></table></div>
</div>
{% endif %}
"""

STUDENT_LOGIN_CONTENT = """
<div class="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 py-12 px-4 sm:px-6 lg:px-8"><div class="max-w-md w-full space-y-8 bg-white dark:bg-gray-800 p-10 rounded-xl shadow-lg">
<div><h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">Check Your Application Status</h2></div>
<form class="mt-8 space-y-6" action="{{ url_for('student_login') }}" method="POST"><div class="rounded-md shadow-sm">
<div><label for="email" class="sr-only">Email address</label><input id="email" name="email" type="email" autocomplete="email" required class="appearance-none rounded-md relative block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" placeholder="Enter your registration email"></div>
</div><div><button type="submit" class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">Check Status</button></div></form>
</div></div>
"""

STUDENT_DASHBOARD_CONTENT = """
<div class="max-w-4xl mx-auto py-12 px-4 sm:px-6 lg:px-8"><div class="bg-white dark:bg-gray-800 shadow-xl rounded-lg overflow-hidden">
<div class="p-8"><h2 class="text-2xl font-bold text-gray-900 dark:text-white">Welcome, {{ student.name }}!</h2>
<p class="mt-2 text-gray-600 dark:text-gray-400">Here are the current statuses of your applications.</p>
{% for reg in registrations %}
{% if reg.status != 'Archived' %}
<div class="mt-6 border-t border-gray-200 dark:border-gray-700 pt-6">
    <h3 class="text-xl font-semibold text-indigo-700 dark:text-indigo-400">{{ reg.contest.name }}</h3>
    <dl class="grid grid-cols-1 gap-x-4 gap-y-8 sm:grid-cols-2 mt-4">
        <div class="sm:col-span-1"><dt class="text-sm font-medium text-gray-500 dark:text-gray-400">Application Status</dt>
            <dd class="mt-1 text-lg font-semibold {% if reg.status == 'Accepted' %} text-green-600 dark:text-green-400 {% elif reg.status == 'Denied' %} text-red-600 dark:text-red-400 {% else %} text-yellow-600 dark:text-yellow-400 {% endif %}">{{ reg.status }}</dd>
        </div>
    </dl>
    {% if reg.status == 'Accepted' %}
    <div class="mt-8"><h4 class="text-lg font-semibold text-gray-900 dark:text-white">Your Test Information</h4>
    {% if reg.test_link %}<p class="mt-2 text-gray-600 dark:text-gray-400">Your application has been accepted! Please use the link below to take your test.</p>
    <div class="mt-4"><a href="{{ reg.test_link }}" target="_blank" class="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700">Proceed to Test</a></div>
    {% else %}<p class="mt-2 text-gray-600 dark:text-gray-400">Your test link has not been assigned yet. Please check back later.</p>{% endif %}
    {% if reg.score is not none %}<div class="mt-8"><h5 class="text-md font-semibold text-gray-800 dark:text-gray-200">Your Score</h5><p class="mt-1 text-4xl font-bold text-indigo-600 dark:text-indigo-400">{{ reg.score }} / 100</p></div>{% endif %}</div>
    {% elif reg.status == 'Denied' %}
    <div class="mt-8"><h4 class="text-lg font-semibold text-red-700 dark:text-red-400">Application Update</h4><p class="mt-2 text-gray-600 dark:text-gray-400">We regret to inform you that your application for this contest was not accepted.</p></div>
    {% else %}
    <div class="mt-8"><h4 class="text-lg font-semibold text-yellow-700 dark:text-yellow-400">Application in Review</h4><p class="mt-2 text-gray-600 dark:text-gray-400">Your application is currently being reviewed by our team.</p></div>
    {% endif %}
</div>
{% endif %}
{% endfor %}
{% if past_performance|length > 0 %}
<div class="mt-10 border-t border-gray-200 dark:border-gray-700 pt-6">
    <h2 class="text-xl font-semibold text-gray-800 dark:text-white mb-4">Your Contest History</h2>
    <div class="overflow-x-auto rounded-lg border dark:border-gray-700"><table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700"><thead class="bg-gray-50 dark:bg-gray-700"><tr>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Contest</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Date</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Score</th>
    </tr></thead><tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
    {% for reg in past_performance %}<tr>
        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{{ reg.contest.name }}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{{ reg.contest.date.strftime('%Y-%m-%d') }}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm font-bold text-gray-800 dark:text-white">{{ reg.score if reg.score is not none else 'N/A' }}</td>
    </tr>{% endfor %}
    </tbody></table></div>
</div>
{% endif %}
</div></div></div>
"""

# --- Helper Functions ---
def render_admin_page(content, **kwargs):
    """Helper function to render admin pages with the admin layout template"""
    return render_template_string(ADMIN_LAYOUT_TEMPLATE.replace('{% block admin_content %}{% endblock %}', content), **kwargs)

# --- Route Definitions ---

@app.route('/')
def index():
    contests = Contest.query.filter_by(is_active=True).order_by(Contest.date.asc()).all()
    return render_template_string(LAYOUT_TEMPLATE.replace('{% block content %}{% endblock %}', HOMEPAGE_CONTENT), title="Home", contests=contests)

@app.route('/syllabus')
def syllabus():
    contests = Contest.query.filter(Contest.is_active==True, Contest.syllabus != None, Contest.syllabus != '').order_by(Contest.date.asc()).all()
    return render_template_string(LAYOUT_TEMPLATE.replace('{% block content %}{% endblock %}', SYLLABUS_CONTENT), title="Syllabus", contests=contests)

@app.route('/results')
def public_results():
    contests = Contest.query.filter_by(publish_results=True).order_by(Contest.date.desc()).all()
    return render_template_string(LAYOUT_TEMPLATE.replace('{% block content %}{% endblock %}', PUBLIC_RESULTS_CONTENT), title="Past Contest Results", contests=contests)

@app.route('/register/<int:contest_id>', methods=['GET', 'POST'])
def register(contest_id):
    contest = Contest.query.get_or_404(contest_id)
    if not contest.is_active:
        flash("Registration for this contest is closed.", "error")
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form['email']
        if Student.query.filter_by(email=email, contest_id=contest.id).first():
            flash('You have already registered for this contest with this email address.', 'error')
            return redirect(url_for('register', contest_id=contest.id))
        
        new_student = Student(
            name=request.form['name'], email=email, college=request.form['college'],
            branch=request.form['branch'], graduation_year=request.form['graduation_year'],
            contest_id=contest.id
        )
        db.session.add(new_student)
        db.session.commit()
        flash(f'You have successfully registered for {contest.name}! Please log in to check your status.', 'success')
        return redirect(url_for('student_login'))
        
    return render_template_string(LAYOUT_TEMPLATE.replace('{% block content %}{% endblock %}', REGISTER_CONTENT), title=f"Register for {contest.name}", contest=contest)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))
    
    # Get client IP address
    client_ip = request.remote_addr
    
    # Check if IP is locked out
    if is_ip_locked_out(client_ip):
        remaining_time = LOGIN_LOCKOUT_TIME - (time.time() - failed_login_attempts[client_ip][1])
        flash(f'Too many failed attempts. Please try again in {int(remaining_time)} seconds.', 'error')
        return render_template_string(LAYOUT_TEMPLATE.replace('{% block content %}{% endblock %}', ADMIN_LOGIN_CONTENT), title="Admin Login", is_first_admin=(Admin.query.count() == 0))
    
    if request.method == 'POST':
        action = request.form.get('action', 'login')
        
        if action == 'login':
            # Handle login
            username = request.form['username']
            password = request.form['password']
            app.logger.info(f"Login attempt: username={username}, IP={client_ip}")
            admin = Admin.query.filter_by(username=username).first()
            if admin:
                app.logger.info(f"Admin found: {admin.username}")
                if admin.check_password(password):
                    app.logger.info("Password verified, login success")
                    log_security_event("LOGIN_SUCCESS", f"Admin {username} logged in successfully", client_ip, username)
                    session['admin_id'] = admin.id
                    # Reset failed attempts on successful login
                    if client_ip in failed_login_attempts:
                        del failed_login_attempts[client_ip]
                    return redirect(url_for('admin_dashboard'))
                else:
                    app.logger.info("Password verification failed")
                    log_security_event("LOGIN_FAILED", f"Invalid password for admin {username}", client_ip, username)
                    record_failed_attempt(client_ip)
            else:
                app.logger.info("Admin not found")
                log_security_event("LOGIN_FAILED", f"Login attempt with non-existent username: {username}", client_ip, username)
                record_failed_attempt(client_ip)
            flash('Invalid username or password.', 'error')
            
        elif action == 'register':
            # Handle registration with security code validation
            username = request.form['reg_username']
            password = request.form['reg_password']
            confirm_password = request.form['reg_confirm_password']
            security_code = request.form.get('security_code', '')
            
            # Check if this is the first admin user
            existing_admin_count = Admin.query.count()
            is_first_admin = existing_admin_count == 0
            
            # Validation
            if not username or not password:
                flash('Username and password are required.', 'error')
            elif password != confirm_password:
                flash('Passwords do not match.', 'error')
            elif len(password) < 6:
                flash('Password must be at least 6 characters long.', 'error')
            elif Admin.query.filter_by(username=username).first():
                flash('Username already exists.', 'error')
            elif not security_code:
                flash('Security code is required for admin registration.', 'error')
            elif security_code != ADMIN_REGISTRATION_CODE:
                flash('Invalid security code. Admin registration is restricted.', 'error')
                log_security_event("REGISTRATION_FAILED", f"Failed admin registration attempt with invalid security code for username: {username}", client_ip, username)
                app.logger.warning(f"Failed admin registration attempt with invalid security code from IP: {client_ip}")
                # Record this as a failed attempt
                record_failed_attempt(client_ip)
            else:
                # Create new admin
                new_admin = Admin(username=username)
                new_admin.set_password(password)
                db.session.add(new_admin)
                db.session.commit()
                
                log_security_event("REGISTRATION_SUCCESS", f"New admin account created: {username}", client_ip, username)
                
                if is_first_admin:
                    flash(f'First admin account "{username}" created successfully! You can now login.', 'success')
                else:
                    flash(f'Admin account "{username}" created successfully! You can now login.', 'success')
                
                app.logger.info(f"New admin account created: {username} from IP: {client_ip}")
                return redirect(url_for('admin_login'))
    
    existing_admin_count = Admin.query.count()
    return render_template_string(LAYOUT_TEMPLATE.replace('{% block content %}{% endblock %}', ADMIN_LOGIN_CONTENT), title="Admin Login", is_first_admin=(existing_admin_count == 0))


@app.route('/admin/dashboard', methods=['GET'])
def admin_dashboard():
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    query = Student.query
    contest_id, search, branch, status = request.args.get('contest_id'), request.args.get('search', ''), request.args.get('branch', ''), request.args.get('status', '')
    
    if contest_id: query = query.filter_by(contest_id=int(contest_id))
    if search: query = query.filter(or_(Student.name.ilike(f'%{search}%'), Student.email.ilike(f'%{search}%')))
    if branch: query = query.filter_by(branch=branch)
    if status: query = query.filter_by(status=status)

    students = query.order_by(Student.id.desc()).all()
    stats = {'total': Student.query.count(), 'accepted': Student.query.filter_by(status='Accepted').count(), 'pending': Student.query.filter_by(status='Pending').count(), 'denied': Student.query.filter_by(status='Denied').count()}
    branches = [b.branch for b in db.session.query(Student.branch).distinct()]
    all_contests = Contest.query.order_by(Contest.date.desc()).all()
    return render_admin_page(ADMIN_DASHBOARD_CONTENT, title="Admin Dashboard", students=students, stats=stats, branches=branches, all_contests=all_contests)

@app.route('/admin/contests', methods=['GET', 'POST'])
def admin_manage_contests():
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    if request.method == 'POST':
        time_str = request.form.get('test_time')
        test_time = datetime.strptime(time_str, '%H:%M').time() if time_str else None
        new_contest = Contest(
            name=request.form['name'],
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            test_time=test_time,
            syllabus=request.form.get('syllabus')
        )
        db.session.add(new_contest)
        db.session.commit()
        flash(f"Contest '{new_contest.name}' created successfully.", 'success')
        return redirect(url_for('admin_manage_contests'))
    
    contests = Contest.query.filter(Contest.date >= date.today()).order_by(Contest.date.asc()).all()
    return render_admin_page(ADMIN_MANAGE_CONTESTS_CONTENT, title="Manage Contests", contests=contests)

@app.route('/admin/contests/edit/<int:contest_id>', methods=['GET', 'POST'])
def admin_edit_contest(contest_id):
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    contest = Contest.query.get_or_404(contest_id)
    if request.method == 'POST':
        contest.name = request.form['name']
        contest.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        time_str = request.form.get('test_time')
        contest.test_time = datetime.strptime(time_str, '%H:%M').time() if time_str else None
        contest.syllabus = request.form.get('syllabus')
        db.session.commit()
        flash(f"Contest '{contest.name}' updated successfully.", 'success')
        return redirect(url_for('admin_manage_contests'))
    return render_admin_page(ADMIN_EDIT_CONTEST_CONTENT, title="Edit Contest", contest=contest)

@app.route('/admin/past_contests')
def admin_past_contests():
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    contests = Contest.query.filter(Contest.date < date.today()).order_by(Contest.date.desc()).all()
    return render_admin_page(ADMIN_PAST_CONTESTS_CONTENT, title="Past Contests", contests=contests)

@app.route('/admin/past_contests/<int:contest_id>')
def admin_view_contest_results(contest_id):
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    contest = Contest.query.get_or_404(contest_id)
    students = Student.query.filter_by(contest_id=contest.id).order_by(Student.name).all()
    return render_admin_page(ADMIN_VIEW_RESULTS_CONTENT, title=f"Results for {contest.name}", contest=contest, students=students)

@app.route('/admin/contests/toggle/<int:contest_id>')
def admin_toggle_contest(contest_id):
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    contest = Contest.query.get_or_404(contest_id)
    contest.is_active = not contest.is_active
    db.session.commit()
    flash(f"Contest '{contest.name}' status updated.", 'success')
    return redirect(url_for('admin_manage_contests'))

@app.route('/admin/contests/publish/<int:contest_id>')
def admin_toggle_publish(contest_id):
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    contest = Contest.query.get_or_404(contest_id)
    contest.publish_results = not contest.publish_results
    db.session.commit()
    flash(f"Results for '{contest.name}' are now {'published' if contest.publish_results else 'hidden'}.", 'success')
    return redirect(url_for('admin_past_contests'))

@app.route('/admin/contests/delete/<int:contest_id>')
def admin_delete_contest(contest_id):
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    contest = Contest.query.get_or_404(contest_id)
    db.session.delete(contest)
    db.session.commit()
    flash(f"Contest '{contest.name}' and all its registrations have been deleted.", 'success')
    return redirect(url_for('admin_manage_contests'))

@app.route('/admin/register_admin', methods=['GET', 'POST'])
def admin_register_admin():
    # Redirect to login page since registration is now available there
    return redirect(url_for('admin_login'))

@app.route('/admin/manage_admins')
def admin_manage_admins():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    admins = Admin.query.all()
    return render_admin_page(ADMIN_MANAGE_ADMINS_CONTENT, title="Manage Admin Accounts", admins=admins)

@app.route('/admin/delete_admin/<int:admin_id>', methods=['POST'])
def admin_delete_admin(admin_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    # Prevent deleting the current admin
    if admin_id == session['admin_id']:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin_manage_admins'))
    
    admin = Admin.query.get_or_404(admin_id)
    username = admin.username
    db.session.delete(admin)
    db.session.commit()
    
    flash(f'Admin account "{username}" has been deleted successfully.', 'success')
    return redirect(url_for('admin_manage_admins'))

@app.route('/admin/delete_student/<int:student_id>', methods=['POST'])
def admin_delete_student(student_id):
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash(f'Registration for {student.name} has been deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    setting_key = 'global_test_link'
    if request.method == 'POST':
        link = request.form.get(setting_key)
        setting = ContestSetting.query.filter_by(key=setting_key).first()
        if setting: setting.value = link
        else: db.session.add(ContestSetting(key=setting_key, value=link))
        db.session.commit()
        flash('Global settings saved successfully!', 'success')
        return redirect(url_for('admin_settings'))
    setting = ContestSetting.query.filter_by(key=setting_key).first()
    return render_admin_page(ADMIN_SETTINGS_CONTENT, title="Global Settings", global_test_link=setting.value if setting else "")

@app.route('/admin/email_settings', methods=['GET', 'POST'])
def admin_email_settings():
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    if request.method == 'POST':
        for key in ['mail_username', 'mail_app_password']:
            setting = ContestSetting.query.filter_by(key=key).first()
            if setting: setting.value = request.form.get(key)
            else: db.session.add(ContestSetting(key=key, value=request.form.get(key)))
        db.session.commit()
        flash('Email settings saved successfully!', 'success')
        return redirect(url_for('admin_email_settings'))
    
    settings = {s.key: s.value for s in ContestSetting.query.filter(ContestSetting.key.in_(['mail_username', 'mail_app_password'])).all()}
    return render_admin_page(ADMIN_EMAIL_SETTINGS_CONTENT, title="Email Settings", email_settings=settings)

def configure_mailer():
    username = ContestSetting.query.filter_by(key='mail_username').first()
    password = ContestSetting.query.filter_by(key='mail_app_password').first()
    if username and password and username.value and password.value:
        app.config['MAIL_USERNAME'] = username.value
        app.config['MAIL_DEFAULT_SENDER'] = username.value
        app.config['MAIL_PASSWORD'] = password.value
        return True
    return False

@app.route('/admin/assign_and_email_all')
def assign_and_email_all():
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    
    if not configure_mailer():
        flash('Email settings are not configured. Please configure them first.', 'error')
        return redirect(url_for('admin_email_settings'))

    setting = ContestSetting.query.filter_by(key='global_test_link').first()
    if not setting or not setting.value:
        flash('Please set a global test link in Global Settings first.', 'error')
        return redirect(url_for('admin_settings'))

    students_to_notify = Student.query.filter_by(status='Accepted', test_link=None).all()
    if not students_to_notify:
        flash('No new accepted students to notify.', 'info')
        return redirect(url_for('admin_dashboard'))
    
    count = 0
    with mail.connect() as conn:
        for student in students_to_notify:
            student.test_link = setting.value
            subject = f"Your Coding Contest Link: {student.contest.name}"
            body = f"Hello {student.name},\n\nCongratulations! Your application for {student.contest.name} has been accepted.\n\nPlease use the following link to access your test:\n{student.test_link}\n\nGood luck!\nThe CodeFest Team"
            msg = Message(subject, recipients=[student.email], body=body)
            try:
                conn.send(msg)
                count += 1
            except Exception as e:
                print(f"Failed to send email to {student.email}: {e}")
                flash(f"Failed to send email to {student.email}. Check credentials and connection.", "error")

    db.session.commit()
    flash(f'Assigned test link and sent notifications to {count} students.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/manual_registration', methods=['GET', 'POST'])
def admin_manual_registration():
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    if request.method == 'POST':
        email, contest_id = request.form['email'], int(request.form['contest_id'])
        if Student.query.filter_by(email=email, contest_id=contest_id).first():
            flash(f"Student with email {email} is already registered for this contest.", 'error')
        else:
            new_student = Student(name=request.form['name'], email=email, college=request.form['college'], branch=request.form['branch'], graduation_year=request.form['graduation_year'], contest_id=contest_id)
            db.session.add(new_student)
            db.session.commit()
            flash(f"Student {new_student.name} registered successfully.", 'success')
            return redirect(url_for('admin_dashboard'))
    contests = Contest.query.filter_by(is_active=True).all()
    return render_admin_page(ADMIN_MANUAL_REG_CONTENT, title="Manual Registration", contests=contests)

@app.route('/admin/edit_student/<int:student_id>', methods=['GET', 'POST'])
def admin_edit_student(student_id):
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    student = Student.query.get_or_404(student_id)
    if request.method == 'POST':
        student.name, student.email, student.college, student.branch, student.graduation_year, student.status = request.form['name'], request.form['email'], request.form['college'], request.form['branch'], request.form['graduation_year'], request.form['status']
        db.session.commit()
        flash(f"Details for {student.name} have been updated.", 'success')
        return redirect(url_for('admin_dashboard'))
    
    past_performance = Student.query.filter(Student.email == student.email, Student.id != student.id, Student.score.isnot(None)).all()
    return render_admin_page(ADMIN_EDIT_STUDENT_CONTENT, title="Edit Student", student=student, branches=["CSE", "ECE", "EIE", "ME", "EEE", "Civil"], past_performance=past_performance)




@app.route('/admin/update_status/<int:student_id>/<string:status>')
def update_status(student_id, status):
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    student = Student.query.get_or_404(student_id)
    if status in ['Accepted', 'Denied']:
        student.status = status
        db.session.commit()
        flash(f"Student {student.name}'s application has been {status.lower()}.", 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/export/pdf')
def admin_export_pdf():
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    students = Student.query.filter(Student.score.isnot(None)).order_by(Student.score.desc()).all()
    if not students:
        flash('No students with scores found to export.', 'error')
        return redirect(url_for('admin_dashboard'))
    pdf = PDF()
    pdf.add_page()
    table_data = [('Rank', 'Name', 'Email', 'Branch', 'Score')] + [(i + 1, s.name, s.email, s.branch, str(s.score)) for i, s in enumerate(students)]
    pdf.create_table(table_data, title='Student Score Leaderboard')
    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers.set('Content-Disposition', 'attachment', filename='student_scores.pdf')
    response.headers.set('Content-Type', 'application/pdf')
    return response

@app.route('/admin/export/csv')
def admin_export_csv():
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    students = Student.query.all()
    if not students:
        flash('No students found to export.', 'error')
        return redirect(url_for('admin_dashboard'))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Email', 'College', 'Branch', 'Graduation Year', 'Status', 'Test Link', 'Score', 'Contest'])
    for s in students:
        writer.writerow([s.id, s.name, s.email, s.college, s.branch, s.graduation_year, s.status, s.test_link, s.score, s.contest.name])
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers.set('Content-Disposition', 'attachment', filename='all_students.csv')
    response.headers.set('Content-Type', 'text/csv')
    return response

@app.route('/admin/update_test_info/<int:student_id>', methods=['POST'])
def update_test_info(student_id):
    if 'admin_id' not in session: return redirect(url_for('admin_login'))
    student = Student.query.get_or_404(student_id)
    student.test_link = request.form.get('test_link')
    score = request.form.get('score')
    student.score = int(score) if score and score.isdigit() else None
    db.session.commit()
    flash(f"Information for {student.name} has been updated.", 'success')
    
    # Redirect back to the page the admin was on
    referrer = request.referrer
    if referrer and 'past_contests' in referrer:
        return redirect(url_for('admin_view_contest_results', contest_id=student.contest_id))
    return redirect(url_for('admin_dashboard'))

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if 'student_email' in session: return redirect(url_for('student_dashboard'))
    if request.method == 'POST':
        student = Student.query.filter_by(email=request.form['email']).first()
        if student:
            session['student_email'] = student.email
            return redirect(url_for('student_dashboard'))
        flash('No application found with that email address.', 'error')
    return render_template_string(LAYOUT_TEMPLATE.replace('{% block content %}{% endblock %}', STUDENT_LOGIN_CONTENT), title="Student Login")

@app.route('/student/dashboard')
def student_dashboard():
    if 'student_email' not in session: return redirect(url_for('student_login'))
    
    email = session['student_email']
    registrations = Student.query.filter_by(email=email).order_by(Student.id.desc()).all()
    
    if not registrations:
        session.pop('student_email', None)
        flash('No applications found for your email.', 'error')
        return redirect(url_for('student_login'))

    # Separate current/pending registrations from past performance
    current_registrations = [r for r in registrations if r.score is None]
    past_performance = [r for r in registrations if r.score is not None]

    return render_template_string(
        LAYOUT_TEMPLATE.replace('{% block content %}{% endblock %}', STUDENT_DASHBOARD_CONTENT), 
        title="My Dashboard", 
        student=registrations[0], 
        registrations=current_registrations,
        past_performance=past_performance
    )

@app.route('/logout')
def logout():
    session.pop('admin_id', None)
    session.pop('student_email', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

# --- Security Configuration ---
ADMIN_REGISTRATION_CODE = "HRISHABHADMIN2025"  # Secure alphanumeric code required for admin registration
MAX_LOGIN_ATTEMPTS = 5  # Maximum failed login attempts before temporary lockout
LOGIN_LOCKOUT_TIME = 300  # Lockout time in seconds (5 minutes)

# Track failed login attempts
failed_login_attempts = {}

def is_ip_locked_out(ip_address):
    """Check if an IP address is temporarily locked out due to failed login attempts"""
    if ip_address in failed_login_attempts:
        attempts, timestamp = failed_login_attempts[ip_address]
        if attempts >= MAX_LOGIN_ATTEMPTS:
            if time.time() - timestamp < LOGIN_LOCKOUT_TIME:
                return True
            else:
                # Reset after lockout period
                del failed_login_attempts[ip_address]
    return False

def record_failed_attempt(ip_address):
    """Record a failed login attempt for an IP address"""
    current_time = time.time()
    if ip_address in failed_login_attempts:
        attempts, _ = failed_login_attempts[ip_address]
        failed_login_attempts[ip_address] = (attempts + 1, current_time)
    else:
        failed_login_attempts[ip_address] = (1, current_time)

def log_security_event(event_type, details, ip_address=None, username=None):
    """Log security events for monitoring and auditing"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ip = ip_address or 'Unknown'
    user = username or 'Unknown'
    
    log_message = f"[SECURITY] {timestamp} | {event_type} | IP: {ip} | User: {user} | Details: {details}"
    app.logger.warning(log_message)

if __name__ == '__main__':
    instance_path = os.path.join(basedir, 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
    with app.app_context():
        db.create_all()
        if not Admin.query.first():
            admin = Admin(username='admin')
            admin.set_password('password')
            db.session.add(admin)
            db.session.commit()
            app.logger.info("Default admin user created: admin / password")
    app.run(debug=True)












