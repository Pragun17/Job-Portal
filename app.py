from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Job, Application

app = Flask(__name__)
app.config['SECRET_KEY'] = 'naukri_secret_key_12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///naukri.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    query = request.args.get('query', '')
    location = request.args.get('location', '')
    jobs_query = Job.query
    if query:
        jobs_query = jobs_query.filter(Job.title.ilike(f'%{query}%') | Job.description.ilike(f'%{query}%'))
    if location:
        jobs_query = jobs_query.filter(Job.location.ilike(f'%{location}%'))
    jobs = jobs_query.order_by(Job.created_at.desc()).all()
    return render_template('index.html', jobs=jobs, query=query, location=location)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        company_name = request.form.get('company_name') if role == 'employer' else None
        resume = request.form.get('resume') if role == 'employee' else None

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already registered.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='scrypt')
        new_user = User(
            name=name,
            email=email,
            password=hashed_password,
            role=role,
            company_name=company_name,
            resume=resume
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            if user.role == 'employer':
                return redirect(url_for('employer_dashboard'))
            else:
                return redirect(url_for('employee_dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/employee/dashboard')
@login_required
def employee_dashboard():
    if current_user.role != 'employee':
        flash('Access unauthorized.', 'danger')
        return redirect(url_for('index'))
    applications = Application.query.filter_by(employee_id=current_user.id).all()
    return render_template('dashboard_employee.html', applications=applications)

@app.route('/employer/dashboard')
@login_required
def employer_dashboard():
    if current_user.role != 'employer':
        flash('Access unauthorized.', 'danger')
        return redirect(url_for('index'))
    jobs = Job.query.filter_by(employer_id=current_user.id).all()
    return render_template('dashboard_employer.html', jobs=jobs)

@app.route('/job/post', methods=['GET', 'POST'])
@login_required
def post_job():
    if current_user.role != 'employer':
        flash('Only employers can post jobs.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        title = request.form.get('title')
        company = current_user.company_name or request.form.get('company')
        location = request.form.get('location')
        job_type = request.form.get('job_type')
        salary = request.form.get('salary')
        description = request.form.get('description')

        new_job = Job(
            title=title,
            company=company,
            location=location,
            job_type=job_type,
            salary=salary,
            description=description,
            employer_id=current_user.id
        )
        db.session.add(new_job)
        db.session.commit()
        flash('Job posted successfully!', 'success')
        return redirect(url_for('employer_dashboard'))
    return render_template('post_job.html')

@app.route('/job/<int:job_id>')
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    has_applied = False
    if current_user.is_authenticated and current_user.role == 'employee':
        existing_app = Application.query.filter_by(job_id=job.id, employee_id=current_user.id).first()
        if existing_app:
            has_applied = True
    return render_template('job_detail.html', job=job, has_applied=has_applied)

@app.route('/job/<int:job_id>/apply', methods=['POST'])
@login_required
def apply_job(job_id):
    if current_user.role != 'employee':
        flash('Only employees can apply for jobs.', 'danger')
        return redirect(url_for('job_detail', job_id=job_id))
    
    existing_app = Application.query.filter_by(job_id=job_id, employee_id=current_user.id).first()
    if existing_app:
        flash('You have already applied for this job.', 'warning')
        return redirect(url_for('job_detail', job_id=job_id))

    new_app = Application(job_id=job_id, employee_id=current_user.id)
    db.session.add(new_app)
    db.session.commit()
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('job_detail', job_id=job_id))

@app.route('/job/<int:job_id>/applicants')
@login_required
def view_applicants(job_id):
    job = Job.query.get_or_404(job_id)
    if job.employer_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('employer_dashboard'))
    return render_template('view_applicants.html', job=job)

if __name__ == '__main__':
    app.run(debug=True)
