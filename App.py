import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import datetime

# إعداد التطبيق
app = Flask(__name__)
app.secret_key = "supersecretkey"
UPLOAD_FOLDER = "uploads"
DB_FILE = "grades.db"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# إنشاء قاعدة البيانات عند بدء التشغيل
def create_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # إنشاء جدول لتتبع التحديثات
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS update_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()


create_database()


@app.route('/')
def splash():
    return render_template('splash.html')


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == "19841984":
            return redirect(url_for('admin_dashboard'))
        else:
            flash("❌ الرمز السري غير صحيح!", "error")
    return render_template('admin_login.html')


@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('admin_dashboard.html')


@app.route('/zyona', methods=['GET', 'POST'])
def zayona():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        if file and file.filename.endswith('.xlsx'):
            df = pd.read_excel(file)

            # التحقق من الأعمدة المطلوبة
            required_columns = {'الرقم المميز', 'اسم الطالب'}
            if not required_columns.issubset(df.columns):
                return "❌ الملف لا يحتوي على الأعمدة المطلوبة!", 400

            # حذف الجدول وإعادة إنشائه
            cursor.execute("DROP TABLE IF EXISTS grades")
            columns = ["student_id INTEGER PRIMARY KEY", "student_name TEXT"]
            columns += [f"'{col}' INTEGER" for col in df.columns if "الامتحان" in col]
            cursor.execute(f"CREATE TABLE grades ({', '.join(columns)})")

            # إدخال البيانات الجديدة
            for _, row in df.iterrows():
                values = [row["الرقم المميز"], row["اسم الطالب"]]
                values += [row[col] if col in row and not pd.isna(row[col]) else None for col in df.columns if
                           "الامتحان" in col]
                placeholders = ", ".join(["?"] * len(values))
                cursor.execute(f"INSERT INTO grades VALUES ({placeholders})", values)

            # تحديث وقت آخر رفع
            cursor.execute("DELETE FROM update_log")
            upload_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO update_log (timestamp) VALUES (?)", (upload_time,))

            conn.commit()
            conn.close()
            return redirect(url_for('edit_exam'))

    conn.close()
    return render_template('Zayona.html')


@app.route('/parent', methods=['GET', 'POST'])
def parent():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        institute = request.form.get('institute')

        if not student_id or not institute:
            return render_template('parent.html', error="❌ الرجاء إدخال جميع الحقول!")

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # جلب أسماء الأعمدة
        cursor.execute("PRAGMA table_info(grades)")
        columns = [col[1] for col in cursor.fetchall()]

        # البحث عن بيانات الطالب
        cursor.execute(f"SELECT * FROM grades WHERE student_id = ?", (student_id,))
        student_data = cursor.fetchone()

        conn.close()

        if student_data:
            student_dict = dict(zip(columns, student_data))
            return render_template('parent_results.html', student=student_dict, institute=institute)
        else:
            return render_template('parent.html', error="⚠️ لم يتم العثور على بيانات لهذا الرقم!")

    return render_template('parent.html')


@app.route('/edit_exam', methods=['GET', 'POST'])
def edit_exam():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if request.method == 'POST':
        student_ids = request.form.getlist('student_id[]')
        student_names = request.form.getlist('student_name[]')

        cursor.execute("PRAGMA table_info(grades)")
        all_columns = [col[1] for col in cursor.fetchall()]
        exam_columns = [col for col in all_columns if "الامتحان" in col]

        for i in range(len(student_ids)):
            student_id = student_ids[i]
            student_name = student_names[i]
            cursor.execute("UPDATE grades SET student_name = ? WHERE student_id = ?", (student_name, student_id))

            for exam_col in exam_columns:
                grade_value = request.form.get(f'grades[{student_id}][{exam_col}]', "").strip()
                if grade_value:
                    cursor.execute(f"UPDATE grades SET '{exam_col}' = ? WHERE student_id = ?",
                                   (grade_value, student_id))

        cursor.execute("DELETE FROM update_log")
        update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO update_log (timestamp) VALUES (?)", (update_time,))

        conn.commit()
        conn.close()
        return redirect(url_for('edit_exam'))

    cursor.execute("SELECT timestamp FROM update_log ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    last_update = result[0] if result else "لا يوجد تحديثات بعد"

    cursor.execute("PRAGMA table_info(grades)")
    all_columns = [col[1] for col in cursor.fetchall()]
    exam_columns = [col for col in all_columns if "الامتحان" in col]

    query = f"SELECT student_id, student_name, {', '.join(exam_columns)} FROM grades" if exam_columns else "SELECT student_id, student_name FROM grades"
    cursor.execute(query)
    students = [dict(zip([desc[0] for desc in cursor.description], row)) for row in cursor.fetchall()]

    conn.close()
    return render_template('edit_exam.html', students=students, exam_columns=exam_columns, last_update=last_update)


if __name__ == '__main__':
    app.run(debug=True)