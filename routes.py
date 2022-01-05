from phenopi.models import User, Picam, Experiments, PiImages
from flask import render_template, url_for, flash, redirect, request
from phenopi.forms import RegistrationForm, LoginForm, ResetPasswordForm, RequestResetForm, AddPiForm, ContactForm, PiScheduleForm, ExpScheduleForm, MultiCheckboxField
from phenopi import app, db, bcrypt
from flask_login import login_user, current_user, logout_user, login_required
from phenopi.utils import contact_request, pi_gif, generate_schedule, cancel_imaging, save_picture
from pathlib import Path

posts = [
    {
        'author': 'Brian',
        'title': 'Message Board',
        'content': 'Just making a message board to house any info from the greenhouse, stuff of that nature?',
        'date_posted': 'today'
    }
]


@app.route("/")
@app.route("/home")
def home():
    if current_user.is_authenticated:
        user = current_user
    else:
        user = None
    return render_template('home.html', posts=posts, user=user)


@app.route("/about")
def about():
    if current_user.is_authenticated:
        user = current_user
    else:
        user = None
    return render_template('about.html', title='About Page', user=user)


@app.route("/register", methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash(f'Account created for {form.username.data}', 'success')
        return redirect(url_for('home'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        user = current_user
    else:
        user = None
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form, user=user)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    # if current_user.is_authenticated:
    #     return redirect(url_for('main.home'))
    # form = RequestResetForm()
    # if form.validate_on_submit():
    #     user = User.query.filter_by(email=form.email.data).first()
    #     send_reset_email(user)
    #     flash('An email has been sent with instructions to reset your password', 'info')
    #     return redirect(url_for('users.login'))
    return render_template('about.html', title='Reset Password')


@app.route("/pidashboard")
def pi_dashboard():
    # need to add a "schedule multiple pis for experiment" button in this view which will be the form for timelapse, but with some click boxes or something 
    # available pis will have to be a variable (ie, not already scheduled)
    
    
    if current_user.is_authenticated:
        user = current_user
    else:
        user = None
    pis = Picam.query.all()

    # loop through the pis in the app and designate the imagefile to use most recent image if in experiment
    for pi in pis:
        if pi.status != 'idle':
            exp = Experiments.query.filter_by(pi_id=pi.id, status='Running').first() # get experiment info
            if exp:
                exp_img = PiImages.query.filter_by(exp_id=exp.id).first()
                if exp_img:
                    # make sure the image hasn't been removed from the computer 
                    if Path(exp_img.image_fname).is_file(): 
                        print(Path(exp_img.image_fname))  # what is image being called?  Is path messed up from multi pi exp?
                        # convert image to small thumbnail
                        profile_pic = save_picture(exp_img.image_fname, pi.piname)
                        pi.image_file = profile_pic
                        db.session.commit()
                    else:
                        continue # leave this until I can sort out if image has correct path first
                        pi.image_file = 'default.png'
                        # commit the profile image thumbnail to the picam table
                        db.session.commit()
                else:
                    pi.image_file = 'default.png'
                    # commit the profile image thumbnail to the picam table
                    db.session.commit()
            else:
                pi.image_file = 'default.png'
                db.session.commit()
        else:
            pi.image_file = 'default.png'
            db.session.commit()

    return render_template('pidashboard.html', picam=pis, title='Pi Dashboard', user=user)


@app.route("/pidashboard/add_pi", methods=['GET', 'POST'])
@login_required
def add_pi():
    if current_user.is_authenticated:
        user = current_user
        form = AddPiForm()
        if form.validate_on_submit():
            pi = Picam(piname=form.pi_name.data, username=form.pi_user.data, hostname=form.hostname.data)
            db.session.add(pi)
            db.session.commit()
            flash(f'Raspberry Pi {form.pi_name.data} added successfully', 'success')

            # create a directory for the images from that pi to be saved on the server
            profile_pics = Path(f'phenopi/static/{form.pi_name.data}/profile_pics/')
            profile_pics.mkdir(parents=True, exist_ok=True)

            # create a directory for cron jobs to live
            cronjobs = Path(f'phenopi/static/{form.pi_name.data}/cronjobs/')
            cronjobs.mkdir(parents=True, exist_ok=True)

            return redirect(url_for('pi_dashboard'))
        return render_template('register_pi.html', title='Register', user=user, form=form)
    return redirect(url_for('pi_dashboard'))


@app.route("/pidashboard/<int:pi_name>/", methods=['GET'])
def pi_config(pi_name):
    if current_user.is_authenticated:
        user = current_user
    else:
        user = None
    picam = Picam.query.filter_by(id=pi_name).first()
    print(picam)
    exp = Experiments.query.filter_by(pi_id=pi_name).order_by(Experiments.date_submitted.desc()).first()
    print(exp)

    return render_template('pi.html', pi=picam, experiment=exp, user=user)


@app.route("/pidashboard/<int:pi_name>/cancel", methods=['GET', 'POST'])
@login_required
def cancel_timelapse(pi_name):
    if current_user.is_authenticated:
        pi = Picam.query.filter_by(id=pi_name).first()
        exp = Experiments.query.filter_by(pi_id=pi_name).order_by(Experiments.date_submitted.desc()).first()
        
        # cancel the imaging by resetting the cron job in the pi and setting pi/exp to idle and cancelled
        cancel_imaging(pi)
        pi.status = 'idle'
        exp.status = 'cancelled'
        db.session.commit()
        flash('Timelapse has been successfully cancelled', 'success')
        return redirect(url_for('pi_dashboard'))
    
    
@app.route("/pidashboard/<int:pi_name>/cancel_exp", methods=['GET', 'POST'])
@login_required
def cancel_experiment(pi_name):
    # stop timelapse of multiple pis if they are linked to same experiment
    if current_user.is_authenticated:
        pi_exp = Experiments.query.filter_by(pi_id=pi_name).first()  # get experiment details from pi you connected to
        print(pi_exp.exp_name)
        
        pis = Experiments.query.filter(Experiments.exp_name.contains(pi_exp.exp_name)).all() # get all other pis with same experiment name [id]
        
        for pi in pis:
            print(pi)
            pi_in_exp = Picam.query.filter_by(id=pi.pi_id).first()  # get picam 
            print(pi_in_exp)
            cancel_imaging(pi_in_exp)
            pi_in_exp.status = 'idle'  # make pi idle
            print(pi.status)
            pi.status = 'cancelled'  # set experiment as cancelled for this experiment entry in db
            print(pi.status)
            
        db.session.commit()
        flash('Experiment has been successfully cancelled', 'success')
    
        return redirect(url_for('pi_dashboard'))


@app.route("/pidashboard/<int:pi_name>/schedule/", methods=['GET', 'POST'])
@login_required
def pi_schedule(pi_name):
    if current_user.is_authenticated:
        user_id = current_user.id
        form = PiScheduleForm()
        pi = Picam.query.filter_by(id=pi_name).first_or_404()
        if request.method == 'POST' and form.validate():
            experiment_name = form.experiment.data.replace(" ", "_")
            # create a dictionary of the form data to pass into scheduler function
            schedule = {'experiment': experiment_name,
                        'start_date': form.start_date.data,
                        'end_date': form.end_date.data,
                        'start': form.start_images.data,
                        'end': form.end_images.data,
                        'interval': form.interval.data}
            generate_schedule(schedule, pi, user_id)
            pi.status = 'Running'
            ex = Experiments(exp_name=experiment_name, start_date=form.start_date.data,
                             end_date=form.end_date.data, start_time=form.start_images.data,
                             end_time=form.end_images.data, img_interval=form.interval.data,
                             pi_id=pi.id, user_id=current_user.id)
            db.session.add(ex)
            db.session.commit()
            flash('Experiment scheduled successfully', 'success')
            return redirect(url_for('pi_dashboard'))
        return render_template('schedule.html', title='Schedule Pi Imaging', pi_name=pi_name,
                               form=form, user=current_user)
    flash('You need to be logged in to access that page', 'info')
    return redirect(url_for('pi_dashboard'))


@app.route("/post/<int:pi_name>/schedule_pi", methods=['POST'])
@login_required
def run_schedule(pi_name):
    # get the info from the form,

    pi_name = Experiments()
    flash('You have scheduled the pi', 'success')
    return redirect(url_for('pi_experiments.html'))


@app.route("/contact", methods=['GET', 'POST'])
def contact():
    if current_user.is_authenticated:
        user = current_user
    else:
        user = None
    form = ContactForm()
    if form.validate_on_submit():
        f_name = form.firstname.data
        l_name = form.lastname.data
        email = form.email.data
        subject = form.subject.data
        contact_request(f_name, l_name, email, subject)
        flash(f'Your query has been submitted to an Admin, they will get back to you soon at the email provided', 'success')
        return redirect(url_for('home'))
    return render_template('contact.html', form=form, user=user)


@app.route("/experiments")
def scheduled_images():
    if current_user.is_authenticated:
        user = current_user
    else:
        user = None
    listed_exp = Experiments.query.order_by(Experiments.date_submitted.desc())
        
    return render_template('pi_experiments.html', title='Experiments Running', ex=listed_exp, user=user)


@app.route("/experiments/<int:pi_name>/<string:exp>/")
def experiment_view(pi_name, exp):
    ### currently pi images don't load, and it is likely the fact that 2 pis have same experiment name.  Make sure you pick only the 
    ### experiment images from the pi you click?
    
    
    if current_user.is_authenticated:
        user = current_user
    else:
        user = None

    imgs = PiImages.query.filter_by(exp_name=exp, pi_id=pi_name).order_by(PiImages.upload_date.asc())   
    
    # in the case that images are removed from the computer, this will cause an error because the image won't show
    # go throuigh the list and if the image doesn't exist on computer anymore, make it missing img instead
    
    ####  THIS ISN'T WORKING AS INTENDED RIGHT NOW -- IT CALLS ALL IMAGES FALSE AND CHANGES NAME IN DB TO MISSING ####
    
    
    # okay, so all images will be the following path type:  /home/bioinf/pi/phenopi/static/pi_name/experiments/exp_name/image_name
    
    for i in imgs:
        if Path(i.image_fname).is_file():
            print(i.image_fname)
            continue
        else:
            continue 
            i.image_fname = "/home/bioinf/pi/phenopi/static/missing_image.png"
            #db.session.commit()


    return render_template('experiment_view.html', imgs=imgs, user=user, title=exp)
        

# schedule a multi pi experiment based on available pis in system
@app.route("/experimentschedule/", methods=['GET', 'POST'])
@login_required
def exp_schedule():
    if current_user.is_authenticated:
        user_id = current_user.id
       
        form = ExpScheduleForm()  # init the form with the pis available (idle)
        
        if request.method == 'POST' and form.validate():
            picked_pis = form.avail_pis.data  # data from the checkboxes, anything selected returns pi id (INT)

            # create a dictionary of the form data to pass into scheduler function
            experiment_name = form.experiment.data.replace(" ", "_")
            schedule = {'experiment': experiment_name,
                        'start_date': form.start_date.data,
                        'end_date': form.end_date.data,
                        'start': form.start_images.data,
                        'end': form.end_images.data,
                        'interval': form.interval.data}
            
            for pi in picked_pis:
                pi_obj = Picam.query.filter_by(id=pi).first()
                generate_schedule(schedule, pi_obj, user_id)
                pi_obj.status = 'Running'
                
                ex = Experiments(exp_name=experiment_name, start_date=form.start_date.data,
                                end_date=form.end_date.data, start_time=form.start_images.data,
                                end_time=form.end_images.data, img_interval=form.interval.data,
                                pi_id=pi_obj.id, user_id=current_user.id)
                db.session.add(ex)
                
            db.session.commit()
            flash(f'Experiment scheduled successfully', 'success')
            return redirect(url_for('home'))
        return render_template('multipi_schedule.html', title='Schedule Multi Pi Experiment', form=form, user=current_user)
    flash('You need to be logged in to access that page', 'info')
    return redirect(url_for('home'))
    
