import streamlit as st
import sqlite3
import os
from PIL import Image
import pandas as pd
import re
from datetime import date
import base64
from io import BytesIO
import uuid
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import urllib.parse

class JazzWoodwindsLessons:
    def __init__(self):
        st.set_page_config(
            page_title="Jazz Woodwinds Academy",
            page_icon="🎷",
            layout="wide"
        )
        self.inject_custom_css()
        self.update_database_schema()
        self.init_database()

        if 'active_booking_id' not in st.session_state:
            st.session_state['active_booking_id'] = None

    def inject_custom_css(self):
        custom_css = """
        <style>
        .offering-card {
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            margin: 10px;
            box-shadow: 2px 2px 12px rgba(0,0,0,0.1);
            transition: transform 0.2s;
            background-color: #ffffff;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .offering-card:hover {
            transform: scale(1.02);
            box-shadow: 4px 4px 20px rgba(0,0,0,0.2);
        }
        .offering-image {
            width: 100%;
            height: 200px;
            object-fit: cover;
            border-radius: 10px 10px 0 0;
        }
        .offering-title {
            font-size: 1.5rem;
            font-weight: bold;
            margin-top: 15px;
            margin-bottom: 10px;
            text-align: center;
        }
        .offering-description {
            font-size: 1rem;
            color: #555555;
            margin-bottom: 15px;
            text-align: center;
            flex-grow: 1;
        }
        .offering-price {
            font-size: 1.2rem;
            font-weight: bold;
            color: #007AFF;
            margin-bottom: 15px;
            text-align: center;
        }
        .book-button {
            display: flex;
            justify-content: center;
        }
        </style>
        """
        st.markdown(custom_css, unsafe_allow_html=True)


    def update_database_schema(self):
        conn = sqlite3.connect('jazz_woodwinds.db')
        c = conn.cursor()
        
        # Add new columns if they don't exist
        try:
            c.execute("ALTER TABLE lesson_bookings ADD COLUMN status TEXT DEFAULT 'Pending'")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            c.execute("ALTER TABLE lesson_bookings ADD COLUMN admin_notes TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        conn.commit()
        conn.close()

    def init_database(self):
        pass

    def get_image_base64(self, image_path):
        """Convert image to base64 string with caching"""
        if not image_path:
            return ""
        
        # Use session state for caching
        cache_key = f"image_cache_{image_path}"
        if cache_key in st.session_state:
            return st.session_state[cache_key]
        
        try:
            with Image.open(image_path) as img:
                # Resize image to reduce size while maintaining aspect ratio
                max_size = (800, 800)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Convert to RGB if needed
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Save to buffer with optimization
                buffer = BytesIO()
                img.save(buffer, format='JPEG', optimize=True, quality=85)
                img_str = base64.b64encode(buffer.getvalue()).decode()
                
                # Cache the result
                st.session_state[cache_key] = img_str
                return img_str
        except Exception as e:
            print(f"Error loading image {image_path}: {e}")
            return ""

    def fetch_offerings(self):
        conn = sqlite3.connect('jazz_woodwinds.db')
        c = conn.cursor()
        c.execute("SELECT id, name, description, price, image_path FROM lesson_offerings")
        offerings = c.fetchall()
        conn.close()
        return offerings


    def fetch_bookings(self):
        conn = sqlite3.connect('jazz_woodwinds.db')
        c = conn.cursor()
        c.execute('''
            SELECT 
                b.id, 
                o.name AS lesson_name, 
                b.student_name, 
                b.student_email, 
                b.preferred_day, 
                b.preferred_time, 
                b.musical_goals,
                b.status,
                b.admin_notes
            FROM lesson_bookings b
            JOIN lesson_offerings o ON b.lesson_id = o.id
            ORDER BY 
                CASE b.preferred_day
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                    WHEN 'Saturday' THEN 6
                    WHEN 'Sunday' THEN 7
                END,
                b.preferred_time
        ''')
        bookings = c.fetchall()
        conn.close()
        return bookings

    def render_landing_page(self):
        st.markdown("""
        <header style="background-color: #000; padding: 50px 0; text-align: center; color: white;">
            <h1 style="font-size: 3.5rem; font-family: 'Helvetica Neue', sans-serif; font-weight: 300; margin: 0;">
                Lessons by Asti
            </h1>
            <p style="font-size: 1.2rem; font-family: 'Helvetica Neue', sans-serif; margin-top: 10px;">
                Master the art of jazz with personalized lessons from a seasoned professional.
            </p>
        </header>
        """, unsafe_allow_html=True)

        st.markdown("<h2 style='text-align: center; margin-top: 50px;'>Our Offerings</h2>", unsafe_allow_html=True)
        offerings = self.fetch_offerings()
        if offerings:
            num_columns = 3 if len(offerings) > 2 else len(offerings)
            cols = st.columns(num_columns)
            for idx, offering in enumerate(offerings):
                with cols[idx % num_columns]:
                    self.render_offering_card(offering)
        else:
            st.info("No offerings available yet. Check back soon!")

        if st.session_state['active_booking_id'] is not None:
            selected_offering = next((off for off in offerings if off[0] == st.session_state['active_booking_id']), None)
            if selected_offering:
                self.render_booking_form(selected_offering)

    def render_offering_card(self, offering):
        image_html = ""
        if offering[4]:  # If there's an image path
            base64_img = self.get_image_base64(offering[4])
            if base64_img:
                image_html = f'<img src="data:image/jpeg;base64,{base64_img}" class="offering-image" alt="{offering[1]}">'
            else:
                image_html = '<div class="offering-image" style="background-color: #f0f0f0;">No image available</div>'
        
        card_html = f"""
        <div class="offering-card">
            {image_html}
            <div class="offering-title">{offering[1]}</div>
            <div class="offering-description">{offering[2]}</div>
            <div class="offering-price">{offering[3]}</div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)
        if st.button("Book This Lesson", key=f"book_{offering[0]}"):
            st.session_state['active_booking_id'] = offering[0]

    def render_booking_form(self, offering):
        st.markdown(f"### Book Lesson: {offering[1]}")
        with st.form(key=f"booking_form_{offering[0]}", clear_on_submit=True):
            student_name = st.text_input("Student Name")
            student_email = st.text_input("Student Email")
            
            # Dropdown for Preferred Day
            preferred_day = st.selectbox(
                "Preferred Day",
                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            )
            
            # Dropdown for Preferred Time
            preferred_time = st.selectbox(
                "Preferred Time",
                ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", 
                 "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM", "6:00 PM"]
            )
            
            musical_goals = st.text_area("What are your musical goals?")
            submitted = st.form_submit_button("Submit Booking")

            if submitted:
                if not student_name or not student_email or not musical_goals:
                    st.error("All fields are required!")
                elif not re.match(r'^\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', student_email):
                    st.error("Please enter a valid email address.")
                else:
                    try:
                        # Save the booking to the database
                        conn = sqlite3.connect('jazz_woodwinds.db')
                        c = conn.cursor()
                        c.execute("""
                            INSERT INTO lesson_bookings 
                            (lesson_id, student_name, student_email, preferred_day, preferred_time, musical_goals)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (offering[0], student_name, student_email, preferred_day, preferred_time, musical_goals))
                        conn.commit()
                        conn.close()
                        
                        st.success(f"Thank you, {student_name}! Your booking for {offering[1]} has been submitted.")
                        st.session_state['active_booking_id'] = None
                    except Exception as e:
                        st.error(f"Error saving booking: {str(e)}")

    def authenticate_admin(self):
        if 'authenticated' not in st.session_state:
            st.session_state['authenticated'] = False

        if not st.session_state['authenticated']:
            st.sidebar.header("Admin Login")
            password = st.sidebar.text_input("Enter Password", type="password")
            if st.sidebar.button("Login"):
                if password == self.get_admin_password():
                    st.session_state['authenticated'] = True
                    st.sidebar.success("Logged in successfully!")
                else:
                    st.sidebar.error("Incorrect password.")
        return st.session_state['authenticated']

    def get_admin_password(self):
        return "onionburger36"

    def render_admin_panel(self):
        """Render the admin panel interface"""
        if not self.authenticate_admin():
            return

        st.title("Admin Dashboard")
        st.markdown("---")
        
        tab1, tab2 = st.tabs(["📚 Lesson Offerings", "📋 Bookings"])
        
        with tab1:
            st.header("Manage Lesson Offerings")
            
            # Add New Offering Section
            with st.expander("➕ Add New Lesson Type", expanded=True):
                with st.form("new_offering_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        name = st.text_input("Lesson Name", placeholder="e.g., Beginner Saxophone")
                        price = st.text_input("Price", placeholder="e.g., $50/hour")
                    with col2:
                        description = st.text_area("Description", 
                            placeholder="Describe what students will learn in this lesson...",
                            height=100)
                        image_file = st.file_uploader("Upload Image (Optional)", 
                            type=['png', 'jpg', 'jpeg'],
                            help="Choose a photo that represents this lesson type")
                    
                    submitted = st.form_submit_button("Add New Lesson Type", use_container_width=True)
                    if submitted:
                        if not name or not description or not price:
                            st.error("Please fill in all required fields!")
                        else:
                            try:
                                image_path = None
                                if image_file:
                                    if not os.path.exists('images'):
                                        os.makedirs('images')
                                    image_filename = f"images/{uuid.uuid4()}.jpg"
                                    with Image.open(image_file) as img:
                                        # Convert to RGB if needed
                                        if img.mode in ('RGBA', 'P'):
                                            img = img.convert('RGB')
                                        # Resize image to a standard size
                                        img.thumbnail((800, 800))
                                        img.save(image_filename, format='JPEG', quality=85, optimize=True)
                                    image_path = image_filename
                                
                                conn = sqlite3.connect('jazz_woodwinds.db')
                                c = conn.cursor()
                                c.execute("""
                                    INSERT INTO lesson_offerings (name, description, price, image_path)
                                    VALUES (?, ?, ?, ?)
                                """, (name, description, price, image_path))
                                conn.commit()
                                conn.close()
                                
                                st.success("✅ New lesson type added successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error adding lesson: {str(e)}")
            
            # View/Delete Offerings Section
            st.markdown("---")
            st.subheader("Current Lesson Types")
            offerings = self.fetch_offerings()
            if offerings:
                for offering in offerings:
                    with st.container():
                        col1, col2, col3 = st.columns([2, 3, 1])
                        with col1:
                            if offering[4]:  # if there's an image
                                try:
                                    img = Image.open(offering[4])
                                    st.image(img, width=200)
                                except:
                                    st.info("Image not available")
                            else:
                                st.info("No image uploaded")
                        
                        with col2:
                            st.markdown(f"### {offering[1]}")
                            st.markdown(f"**Price:** {offering[3]}")
                            st.markdown(offering[2])
                        
                        with col3:
                            if st.button("🗑️ Delete", key=f"del_{offering[0]}", 
                                help="Remove this lesson type"):
                                if st.warning(f"Are you sure you want to delete '{offering[1]}'?"):
                                    conn = sqlite3.connect('jazz_woodwinds.db')
                                    c = conn.cursor()
                                    c.execute("DELETE FROM lesson_offerings WHERE id = ?", (offering[0],))
                                    conn.commit()
                                    conn.close()
                                    st.success("Lesson deleted successfully!")
                                    st.rerun()
                        st.markdown("---")
            else:
                st.info("No lesson types available. Add your first lesson above!")
        
        with tab2:
            st.header("Student Bookings")
            bookings = self.fetch_bookings()
            
            # Add filtering options
            col1, col2 = st.columns(2)
            with col1:
                filter_status = st.selectbox(
                    "Filter by Status",
                    ["All", "Pending", "Confirmed", "Completed", "Cancelled"],
                    key="booking_status_filter"
                )
            with col2:
                filter_day = st.selectbox(
                    "Filter by Day",
                    ["All Days", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                    key="booking_day_filter"
                )

            # Add export functionality
            if bookings:
                df = pd.DataFrame(bookings, columns=[
                    'ID', 
                    'Lesson Type', 
                    'Student Name', 
                    'Email', 
                    'Day', 
                    'Time', 
                    'Musical Goals',
                    'Status',
                    'Admin Notes'
                ])
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Export Bookings to CSV",
                    data=csv,
                    file_name=f"bookings_export_{date.today()}.csv",
                    mime="text/csv",
                )

            if bookings:
                # Group bookings by day for better organization
                st.markdown("### 📅 Upcoming Lessons")
                for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
                    day_bookings = [b for b in bookings if b[4] == day]
                    if day_bookings and (filter_day == "All Days" or filter_day == day):
                        with st.expander(f"{day} Lessons ({len(day_bookings)})", expanded=True):
                            for booking in sorted(day_bookings, key=lambda x: x[5]):  # Sort by time
                                with st.container():
                                    col1, col2, col3 = st.columns([2, 2, 1])
                                    
                                    with col1:
                                        st.markdown(f"**🕒 {booking[5]}**")
                                        st.markdown(f"**Student:** {booking[2]}")
                                        st.markdown(f"**Email:** {booking[3]}")
                                    
                                    with col2:
                                        st.markdown(f"**Lesson:** {booking[1]}")
                                        st.markdown("**Goals:**")
                                        st.markdown(f"_{booking[6]}_")
                                    
                                    with col3:
                                        # Add status management
                                        status = st.selectbox(
                                            "Status",
                                            ["Pending", "Confirmed", "Completed", "Cancelled"],
                                            key=f"status_{booking[0]}",
                                            index=["Pending", "Confirmed", "Completed", "Cancelled"].index(booking[7] or "Pending")
                                        )
                                        
                                        # Update status if changed
                                        if status != booking[7]:
                                            conn = sqlite3.connect('jazz_woodwinds.db')
                                            c = conn.cursor()
                                            c.execute("""
                                                UPDATE lesson_bookings 
                                                SET status = ? 
                                                WHERE id = ?
                                            """, (status, booking[0]))
                                            conn.commit()
                                            conn.close()
                                        
                                        # Add quick actions
                                        if st.button("⏰ Set Reminder", key=f"remind_{booking[0]}"):
                                            if self.set_reminder(
                                                booking_id=booking[0],
                                                student_name=booking[2],
                                                lesson_type=booking[1],
                                                day=booking[4],
                                                time=booking[5]
                                            ):
                                                st.success(f"Reminder set for {booking[2]}'s lesson on {booking[4]} at {booking[5]}")
                                            else:
                                                st.info("Reminder already set for this lesson")
                                        
                                        if st.button("🗑️ Cancel Booking", key=f"cancel_{booking[0]}"):
                                            if st.warning("Are you sure you want to cancel this booking?"):
                                                conn = sqlite3.connect('jazz_woodwinds.db')
                                                c = conn.cursor()
                                                c.execute("DELETE FROM lesson_bookings WHERE id = ?", (booking[0],))
                                                conn.commit()
                                                conn.close()
                                                st.success("Booking cancelled successfully!")
                                                st.rerun()
                                    
                                    # Add notes section
                                    notes = st.text_area(
                                        "Admin Notes",
                                        value=booking[8] or "",  # Use existing notes or empty string
                                        key=f"notes_{booking[0]}",
                                        placeholder="Add any notes about this booking..."
                                    )
                                    
                                    # Update notes if changed
                                    if notes != booking[8]:
                                        conn = sqlite3.connect('jazz_woodwinds.db')
                                        c = conn.cursor()
                                        c.execute("""
                                            UPDATE lesson_bookings 
                                            SET admin_notes = ? 
                                            WHERE id = ?
                                        """, (notes, booking[0]))
                                        conn.commit()
                                        conn.close()
                                    
                                    st.markdown("---")
            else:
                st.info("No bookings received yet.")

            if 'reminders' in st.session_state and st.session_state.reminders:
                st.markdown("### ⏰ Active Reminders")
                for reminder_key, reminder in st.session_state.reminders.items():
                    with st.expander(f"{reminder['student_name']} - {reminder['day']} at {reminder['time']}"):
                        st.markdown(f"**Lesson:** {reminder['lesson_type']}")
                        if st.button("Clear Reminder", key=f"clear_{reminder_key}"):
                            del st.session_state.reminders[reminder_key]
                            st.rerun()

    def set_reminder(self, booking_id, student_name, lesson_type, day, time):
        """Generate calendar event file"""
        if 'reminders' not in st.session_state:
            st.session_state.reminders = {}
        
        reminder_key = f"reminder_{booking_id}"
        if reminder_key not in st.session_state.reminders:
            # Convert day and time to datetime
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            current_time = datetime.now()
            target_day = days.index(day)
            days_ahead = (target_day - current_time.weekday() + 7) % 7
            
            lesson_time = datetime.strptime(time, "%I:%M %p").time()
            lesson_datetime = datetime.combine(
                current_time.date() + timedelta(days=days_ahead),
                lesson_time
            )
            
            # Create ICS content
            ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:{lesson_datetime.strftime("%Y%m%dT%H%M%S")}
DTEND:{(lesson_datetime + timedelta(hours=1)).strftime("%Y%m%dT%H%M%S")}
SUMMARY:Lesson with {student_name}
DESCRIPTION:Type: {lesson_type}
END:VEVENT
END:VCALENDAR"""
            
            # Store in session state
            st.session_state.reminders[reminder_key] = {
                'student_name': student_name,
                'lesson_type': lesson_type,
                'day': day,
                'time': time,
                'ics_content': ics_content,
                'is_set': True
            }
            
            # Offer both Google Calendar and ICS download
            col1, col2 = st.columns(2)
            with col1:
                # Google Calendar link
                calendar_url = (
                    f"https://calendar.google.com/calendar/render?"
                    f"action=TEMPLATE"
                    f"&text={urllib.parse.quote(f'Lesson with {student_name}')}"
                    f"&details={urllib.parse.quote(f'Type: {lesson_type}')}"
                    f"&dates={lesson_datetime.strftime('%Y%m%dT%H%M%S')}/{(lesson_datetime + timedelta(hours=1)).strftime('%Y%m%dT%H%M%S')}"
                )
                st.markdown(f"[Add to Google Calendar]({calendar_url})")
            
            with col2:
                # ICS download
                st.download_button(
                    label="Download Calendar Event",
                    data=ics_content,
                    file_name=f"lesson_{student_name}_{day}.ics",
                    mime="text/calendar"
                )
            
            st.success("✅ Reminder created!")
            return True
        return False

    def get_calendar_service(self):
        """Get or create Google Calendar service"""
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        
        creds = None
        if 'token.json' in os.listdir():
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
                
            # Save the credentials
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        
        return build('calendar', 'v3', credentials=creds)

    def check_reminders(self):
        """Check for due reminders"""
        if 'reminders' in st.session_state:
            current_time = datetime.now()
            reminders_to_remove = []
            
            for reminder_key, reminder in st.session_state.reminders.items():
                if current_time >= reminder['reminder_datetime']:
                    st.warning(f"🔔 **REMINDER:** Lesson with {reminder['student_name']} ({reminder['lesson_type']}) is scheduled for {reminder['time']} today!")
                    reminders_to_remove.append(reminder_key)
            
            # Remove triggered reminders
            for key in reminders_to_remove:
                del st.session_state.reminders[key]

    def main(self):
        st.sidebar.title("Navigation")
        page = st.sidebar.radio("Go to", ["Home", "Admin Panel"])

        if page == "Home":
            self.render_landing_page()
        elif page == "Admin Panel":
            self.render_admin_panel()

if __name__ == "__main__":
    app = JazzWoodwindsLessons()
    app.main()
