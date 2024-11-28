import streamlit as st
import sqlite3
import os
from PIL import Image
import re
from datetime import date
import base64
from io import BytesIO
import uuid

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
        c.execute("""
        CREATE TABLE IF NOT EXISTS lesson_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            student_email TEXT NOT NULL,
            preferred_day TEXT NOT NULL,
            preferred_time TEXT NOT NULL,
            musical_goals TEXT NOT NULL,
            FOREIGN KEY (lesson_id) REFERENCES lesson_offerings (id)
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS lesson_offerings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price TEXT NOT NULL,
            image_path TEXT
        )
        """)
        conn.commit()
        conn.close()

    def init_database(self):
        pass

    def get_image_base64(self, image_path):
        """Convert image to base64 string for embedding"""
        if not image_path or not os.path.exists(image_path):
            return ""
        
        cache_key = f"image_cache_{image_path}"
        if cache_key in st.session_state:
            return st.session_state[cache_key]
        
        try:
            with Image.open(image_path) as img:
                max_size = (800, 800)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                buffer = BytesIO()
                img.save(buffer, format='JPEG', optimize=True, quality=85)
                img_str = base64.b64encode(buffer.getvalue()).decode()
                
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
        SELECT b.id, o.name AS lesson_name, b.student_name, b.student_email, b.preferred_day, b.preferred_time, b.musical_goals
        FROM lesson_bookings b
        JOIN lesson_offerings o ON b.lesson_id = o.id
        ORDER BY b.preferred_day ASC, b.preferred_time ASC
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
        if offering[4]:  # If there's an image path
            base64_img = self.get_image_base64(offering[4])
            if base64_img:
                image_html = f'<img src="data:image/jpeg;base64,{base64_img}" class="offering-image" alt="{offering[1]}">'
        
        card_html = f"""
        <div class="offering-card">
            {image_html}
            <div class="offering-title">{offering[1]}</div>
            <div class="offering-description">{offering[2]}</div>
            <div class="offering-price">{offering[3]}</div>
            <div class="book-button">
                <button onclick="window.location.href='#booking'" style="padding: 10px 20px; background-color: #007AFF; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    Book This Lesson
                </button>
            </div>
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
            preferred_day = st.selectbox("Preferred Day", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
            preferred_time = st.text_input("Preferred Time (e.g., 10:00 AM or 3:30 PM)")
            musical_goals = st.text_area("What are your musical goals?")
            submitted = st.form_submit_button("Submit Booking")
        
        if submitted:
            if not student_name or not student_email or not musical_goals or not preferred_time:
                st.error("All fields are required!")
            elif not re.match(r'^\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', student_email):
                st.error("Please enter a valid email address.")
            else:
                conn = sqlite3.connect('jazz_woodwinds.db')
                c = conn.cursor()
                c.execute("""
                INSERT INTO lesson_bookings (lesson_id, student_name, student_email, preferred_day, preferred_time, musical_goals)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (offering[0], student_name, student_email, preferred_day, preferred_time, musical_goals))
                conn.commit()
                conn.close()
                st.success(f"Thank you, {student_name}! Your booking for {offering[1]} has been submitted.")
                st.session_state['active_booking_id'] = None

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
        return "your_secure_password"

    def render_admin_panel(self):
        if not self.authenticate_admin():
            return
        
        st.title("Admin Dashboard")
        st.markdown("---")
        
        tab1, tab2 = st.tabs(["📚 Lesson Offerings", "📋 Bookings"])
        
        with tab1:
            st.subheader("Manage Lesson Offerings")
            # Original functionality here...
            st.write("Lesson offerings management interface goes here.")

        with tab2:
            st.subheader("Student Bookings")
            bookings = self.fetch_bookings()
            if bookings:
                for booking in bookings:
                    with st.expander(f"📅 {booking[2]} - {booking[1]}", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Student:** {booking[2]}")
                            st.markdown(f"**Email:** {booking[3]}")
                            st.markdown(f"**Preferred Schedule:** {booking[4]}, {booking[5]}")
                        with col2:
                            st.markdown("**Musical Goals:**")
                            st.markdown(f"_{booking[6]}_")
                        
                        if st.button("🗑️ Delete Booking", key=f"del_booking_{booking[0]}"):
                            conn = sqlite3.connect('jazz_woodwinds.db')
                            c = conn.cursor()
                            c.execute("DELETE FROM lesson_bookings WHERE id = ?", (booking[0],))
                            conn.commit()
                            conn.close()
                            st.success("Booking deleted successfully!")
                            st.experimental_rerun()
            else:
                st.info("No bookings received yet.")

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
