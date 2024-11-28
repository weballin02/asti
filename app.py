# app.py
import os
from flask import Flask, render_template, redirect, url_for, flash, request, send_from_directory, abort, jsonify
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import func
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Create Flask app and load config
app = Flask(__name__)
app.config.from_object('config.Config')

# Import extensions
from extensions import db, migrate, login_manager

# Initialize extensions
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# Import models and forms after initializing extensions
from models import User, Video, Comment, Rating, Purchase
from forms import (RegistrationForm, LoginForm, UpdateAccountForm, 
                  CommentForm, RatingForm, UploadForm, UpdateVideoForm)
from utils import save_picture

# Initialize Stripe
import stripe
stripe.api_key = app.config['STRIPE_SECRET_KEY']

# Ensure upload and profile picture folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.root_path, 'static', 'profile_pics'), exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def has_purchased(user_id, video_id):
    purchase = Purchase.query.filter_by(user_id=user_id, video_id=video_id).first()
    return purchase is not None

@app.route("/")
@app.route("/home")
def home():
    videos = Video.query.order_by(Video.date_posted.desc()).all()
    # Calculate average ratings
    for video in videos:
        avg = db.session.query(func.avg(Rating.score)).filter(Rating.video_id == video.id).scalar()
        video.average_rating = round(avg, 2) if avg else 'No ratings yet'
    return render_template('index.html', videos=videos)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_pw = generate_password_hash(form.password.data)
        user = User(username=form.username.data, email=form.email.data, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.bio = form.bio.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.bio.data = current_user.bio
    
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    videos = Video.query.filter_by(uploader=current_user).order_by(Video.date_posted.desc()).all()
    
    return render_template('account.html', title='Account',
                         image_file=image_file, form=form, videos=videos)

@app.route("/user/<string:username>")
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    videos = Video.query.filter_by(uploader=user).order_by(Video.date_posted.desc()).all()
    return render_template('user_profile.html', user=user, videos=videos)

@app.route("/upload", methods=['GET', 'POST'])
@login_required
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        title = form.title.data
        file = form.video.data
        price = form.price.data

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # To prevent filename collisions
            unique_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)

            # Save video info to database
            video = Video(title=title, filename=unique_filename, uploader=current_user, price=price)
            db.session.add(video)
            db.session.commit()

            flash('Video uploaded successfully!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid file type. Allowed types are mp4, mov, avi, mkv.', 'danger')
            return redirect(request.url)
    return render_template('upload.html', title='Upload Video', form=form)

@app.route("/video/<int:video_id>", methods=['GET', 'POST'])
def video_detail(video_id):
    video = Video.query.get_or_404(video_id)
    form_comment = CommentForm()
    form_rating = RatingForm()

    if current_user.is_authenticated:
        has_access = has_purchased(current_user.id, video_id)
    else:
        has_access = False

    if not has_access:
        return redirect(url_for('purchase_video', video_id=video.id))

    if form_comment.validate_on_submit() and 'submit_comment' in request.form:
        comment = Comment(content=form_comment.content.data, video=video, author=current_user)
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been posted!', 'success')
        return redirect(url_for('video_detail', video_id=video.id))

    if form_rating.validate_on_submit() and 'submit_rating' in request.form:
        if not current_user.is_authenticated:
            flash('You need to be logged in to rate videos.', 'danger')
            return redirect(url_for('login'))
        existing_rating = Rating.query.filter_by(video_id=video.id, user_id=current_user.id).first()
        if existing_rating:
            existing_rating.score = form_rating.score.data
            existing_rating.date_rated = datetime.utcnow()
            flash('Your rating has been updated!', 'success')
        else:
            rating = Rating(score=form_rating.score.data, video=video, rater=current_user)
            db.session.add(rating)
            flash('Your rating has been submitted!', 'success')
        db.session.commit()
        return redirect(url_for('video_detail', video_id=video.id))

    average_rating = db.session.query(func.avg(Rating.score)).filter(Rating.video_id == video.id).scalar()
    average_rating = round(average_rating, 2) if average_rating else 'No ratings yet'

    comments = Comment.query.filter_by(video_id=video.id).order_by(Comment.date_commented.desc()).all()

    return render_template('video_detail.html', video=video, comments=comments,
                           form_comment=form_comment, form_rating=form_rating,
                           average_rating=average_rating, has_access=has_access)

@app.route("/purchase/<int:video_id>", methods=['GET', 'POST'])
@login_required
def purchase_video(video_id):
    video = Video.query.get_or_404(video_id)
    if has_purchased(current_user.id, video_id):
        flash('You have already purchased this video.', 'info')
        return redirect(url_for('video_detail', video_id=video.id))
    
    if request.method == 'POST':
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                customer_email=current_user.email,
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': video.title,
                        },
                        'unit_amount': int(video.price * 100),  # Convert to cents
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=url_for('payment_success', video_id=video.id, _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=url_for('payment_cancel', video_id=video.id, _external=True),
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            flash('An error occurred while processing your payment.', 'danger')
            return redirect(url_for('video_detail', video_id=video.id))
    else:
        return render_template('purchase_video.html', video=video, 
                             stripe_public_key=app.config['STRIPE_PUBLIC_KEY'])

@app.route("/payment_success/<int:video_id>")
@login_required
def payment_success(video_id):
    session_id = request.args.get('session_id')
    if not session_id:
        abort(400)

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
            if not has_purchased(current_user.id, video_id):
                purchase = Purchase(user_id=current_user.id, video_id=video_id)
                db.session.add(purchase)
                db.session.commit()
            flash('Payment successful! You now have access to this video.', 'success')
            return redirect(url_for('video_detail', video_id=video_id))
        else:
            flash('Payment was not successful.', 'danger')
            return redirect(url_for('video_detail', video_id=video_id))
    except Exception as e:
        flash('An error occurred while verifying your payment.', 'danger')
        return redirect(url_for('video_detail', video_id=video_id))

@app.route("/payment_cancel/<int:video_id>")
def payment_cancel(video_id):
    flash('Payment was canceled.', 'info')
    return redirect(url_for('video_detail', video_id=video_id))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/stripe_webhook", methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = app.config['STRIPE_WEBHOOK_SECRET']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)

    return jsonify(success=True), 200

def handle_checkout_session(session):
    customer_email = session.get('customer_email')
    video_title = session['display_items'][0]['custom']['name']
    user = User.query.filter_by(email=customer_email).first()
    video = Video.query.filter_by(title=video_title).first()
    if user and video:
        if not has_purchased(user.id, video.id):
            purchase = Purchase(user_id=user.id, video_id=video.id)
            db.session.add(purchase)
            db.session.commit()

@app.route("/video/<int:video_id>/edit", methods=['GET', 'POST'])
@login_required
def edit_video(video_id):
    video = Video.query.get_or_404(video_id)
    if video.uploader != current_user:
        abort(403)  # Forbidden access
    
    form = UpdateVideoForm()
    if form.validate_on_submit():
        video.title = form.title.data
        video.price = form.price.data
        if form.video.data:
            # Delete old video file
            old_video_path = os.path.join(app.config['UPLOAD_FOLDER'], video.filename)
            if os.path.exists(old_video_path):
                os.remove(old_video_path)
            
            # Save new video file
            file = form.video.data
            filename = secure_filename(file.filename)
            unique_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            video.filename = unique_filename

        db.session.commit()
        flash('Your video has been updated!', 'success')
        return redirect(url_for('video_detail', video_id=video.id))
    
    elif request.method == 'GET':
        form.title.data = video.title
        form.price.data = video.price
    
    return render_template('edit_video.html', title='Edit Video',
                         form=form, video=video)

@app.route("/video/<int:video_id>/delete", methods=['POST'])
@login_required
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)
    if video.uploader != current_user:
        abort(403)
    
    # Delete video file
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video.filename)
    if os.path.exists(video_path):
        os.remove(video_path)
    
    # Delete associated comments, ratings, and purchases
    Comment.query.filter_by(video_id=video.id).delete()
    Rating.query.filter_by(video_id=video.id).delete()
    Purchase.query.filter_by(video_id=video.id).delete()
    
    # Delete video record
    db.session.delete(video)
    db.session.commit()
    
    flash('Your video has been deleted!', 'success')
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(debug=True)