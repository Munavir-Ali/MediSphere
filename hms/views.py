from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.db import connection
from datetime import datetime
from django.http import HttpResponseRedirect
from django.urls import reverse
from decimal import Decimal
from django.db import transaction
from datetime import date
import uuid
import logging
from django.utils import timezone

def admin_logout_redirect_to_settings(request):
    for key in ['_auth_user_id', '_auth_user_backend', '_auth_user_hash']:
        request.session.pop(key, None)
    return redirect('admin_settings_page')

logger = logging.getLogger(__name__)

def view_logs(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    search_query = request.GET.get('search', '')
    with connection.cursor() as cursor:
        if search_query:
            cursor.execute("""
                SELECT slog_id, log_time, action, user_id 
                FROM system_logs 
                WHERE user_id LIKE %s OR slog_id LIKE %s
                ORDER BY log_time DESC
            """, [f'%{search_query}%', f'%{search_query}%'])
        else:
            cursor.execute("""
                SELECT slog_id, log_time, action, user_id 
                FROM system_logs 
                ORDER BY log_time DESC
            """)
        logs = cursor.fetchall()
    logs_data = [{
        "slog_id": log[0],
        "log_time": log[1].strftime('%Y-%m-%d %H:%M:%S') if log[1] else '',
        "action": log[2],
        "user_id": log[3]
    } for log in logs]
    paginator = Paginator(logs_data, 10)
    page_number = request.GET.get('page')
    page_logs = paginator.get_page(page_number)
    return render(request, "view_logs.html", {"logs": page_logs,"search_query": search_query})

def log_system_action(user_id, action):
    try:
        if not user_id:
            print("Empty user_id - skipping log")
            return
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM admins WHERE admin_id = %s
                    UNION ALL
                    SELECT 1 FROM doctors WHERE doctor_id = %s
                    UNION ALL
                    SELECT 1 FROM staffs WHERE staff_id = %s
                ) AS user_exists
            """, [user_id, user_id, user_id])
            result = cursor.fetchone()
            if result and result[0]:
                cursor.execute(
                    "INSERT INTO system_logs (action, user_id) VALUES (%s, %s)",
                    [f"{user_id} {action}", user_id]
                )
                print(f"Successfully logged action: {user_id} {action}")
            else:
                print(f"User {user_id} not found in any table - logging anyway")
                cursor.execute(
                    "INSERT INTO system_logs (action, user_id) VALUES (%s, %s)",
                    [f"{user_id} {action}", user_id]
                )
    except Exception as e:
        print(f"Failed to log action: {str(e)}")

def login_view(request):
    if request.method == "POST":
        user_id = request.POST.get("userid")
        password = request.POST.get("password")
        print(f"Login Attempt - User ID: {user_id}, Password: {password}")
        with connection.cursor() as cursor:
            cursor.execute("SELECT admin_id, username FROM admins WHERE admin_id = %s AND password = %s",
                           [user_id, password])
            admin = cursor.fetchone()
        if admin:
            request.session['admin_name'] = admin[1]
            request.session['admin_id'] = admin[0]
            request.session['is_logged_in'] = True
            log_system_action(admin[0], "logged in as admin")
            return redirect('admin_page')
        with connection.cursor() as cursor:
            cursor.execute("SELECT doctor_id, name FROM doctors WHERE doctor_id = %s AND d_password = %s",
                           [user_id, password])
            doctor = cursor.fetchone()
        if doctor:
            request.session['doctor_id'] = doctor[0]
            request.session['doctor_name'] = doctor[1]
            request.session['is_logged_in'] = True
            log_system_action(doctor[0], "logged in as doctor")
            return redirect('doctor_dashboard')
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT staff_id, name, role 
                FROM staffs 
                WHERE staff_id = %s AND password = %s
            """, [user_id, password])
            staff = cursor.fetchone()
        if staff:
            request.session['staff_id'] = staff[0]
            request.session['staff_name'] = staff[1]
            request.session['role'] = staff[2]
            request.session['is_logged_in'] = True
            log_system_action(staff[0], f"logged in as {staff[2]}")
            if staff[2] == "Nurse":
                return redirect('nurse_home')
            return redirect('accountant_home')
        messages.error(request, "Invalid User ID or Password")
    return render(request, "login.html")

def logout_view(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    user_id = (request.session.get('admin_id') or
               request.session.get('doctor_id') or
               request.session.get('staff_id'))
    request.session.flush()
    messages.success(request, "You have been logged out.")
    if user_id:
        log_system_action(user_id, "logged out")
    return redirect('login')

def home(request):
    return redirect('login')

def admin(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    admin_name = request.session.get('admin_name', 'Admin')
    return render(request, "admin_page.html", {"admin_name": admin_name})

def admin_settings_page(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    return render(request,'settings.html')

def doctor_profile_admin(request, doctor_id):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT d.doctor_id, d.name, d.specialty, dept.department_name, d.contact_info, d.shift, d.status, d.department_id
            FROM doctors d
            LEFT JOIN departments dept ON d.department_id = dept.department_id
            WHERE d.doctor_id = %s
        """, [doctor_id])
        doctor = cursor.fetchone()
    if not doctor:
        messages.error(request, "Doctor not found.")
        return redirect('doctors_list')
    from_department = request.GET.get("from_department", "false") == "true"
    doctor_data = {
        "doctor_id": doctor[0],
        "doctor_name": doctor[1],
        "specialty": doctor[2],
        "department": doctor[3],
        "contact_info": doctor[4],
        "shift": doctor[5],
        "status": doctor[6],
        "department_id": doctor[7],
        "from_department": from_department,
    }
    return render(request, "doctor_profile_admin.html", doctor_data)

def update_doctor(request, doctor_id):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    from_department = request.GET.get("from_department", "false") == "true"
    department_id = request.GET.get("department_id", None)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT d.name, d.specialty, d.department_id, dept.department_name, d.contact_info, d.shift, d.status, d.license_number
            FROM doctors d
            LEFT JOIN departments dept ON d.department_id = dept.department_id
            WHERE d.doctor_id = %s
        """, [doctor_id])
        doctor = cursor.fetchone()
    if not doctor:
        messages.error(request, "Doctor not found.")
        return redirect('doctors_list')
    doctor_data = {
        "doctor_id": doctor_id,
        "doctor_name": doctor[0],
        "specialty": doctor[1],
        "department_id": doctor[2],
        "department_name": doctor[3] if doctor[3] else "Not Assigned",
        "contact_info": doctor[4],
        "shift": doctor[5],
        "status": doctor[6],
        "license_number": doctor[7],
        "from_department": from_department,
        "department_id": department_id
    }
    if request.method == "POST":
        name = request.POST.get("name")
        contact_info = request.POST.get("contact_info")
        shift = request.POST.get("shift")
        status = request.POST.get("status")
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE doctors SET name=%s, contact_info=%s, shift=%s, status=%s
                WHERE doctor_id=%s
            """, [name, contact_info, shift, status, doctor_id])
        messages.success(request, "Doctor details updated successfully!")
        if from_department and department_id:
            return HttpResponseRedirect(reverse('department_doctor', kwargs={'department_id': department_id}))
        else:
            return HttpResponseRedirect(reverse('doctor_profile_admin', args=[doctor_id]))
    return render(request, "update_doctor.html", {"doctor": doctor_data})

def update_staff(request, staff_id):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name, role, department_id, contact_info, hire_date, shift, status 
            FROM staffs WHERE staff_id = %s
        """, [staff_id])
        staff = cursor.fetchone()
    if not staff:
        messages.error(request, "Staff not found.")
        return redirect('staffs_list')
    staff_data = {
        "staff_id": staff_id,
        "name": staff[0],
        "role": staff[1],
        "department_id": staff[2],
        "contact_info": staff[3],
        "hire_date": staff[4],
        "shift": staff[5],
        "status": staff[6],
    }
    with connection.cursor() as cursor:
        cursor.execute("SELECT department_id, department_name FROM departments")
        departments = cursor.fetchall()
    department_list = [{"department_id": dept[0], "department_name": dept[1]} for dept in departments]
    if request.method == "POST":
        name = request.POST.get("name")
        role = request.POST.get("role")
        department_id = request.POST.get("department_id") or None
        contact_info = request.POST.get("contact_info")
        shift = request.POST.get("shift")
        status = request.POST.get("status")
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE staffs 
                SET name=%s, role=%s, department_id=%s, contact_info=%s, shift=%s, status=%s 
                WHERE staff_id=%s
            """, [name, role, department_id, contact_info, shift, status, staff_id])
        messages.success(request, "Staff details updated successfully!")
        return redirect('staff_details_admin', staff_id=staff_id)
    return render(request, "update_staff.html", {"staff": staff_data, "departments": department_list})

def update_patient(request, patient_id):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT first_name, last_name, date_of_birth, gender, phone_number, email, address, registration_date 
            FROM patients WHERE patient_id = %s
        """, [patient_id])
        patient = cursor.fetchone()
    if not patient:
        messages.error(request, "Patient not found.")
        return redirect('patients_list')
    patient_data = {
        "patient_id": patient_id,
        "first_name": patient[0],
        "last_name": patient[1],
        "date_of_birth": patient[2],
        "gender": patient[3],
        "phone_number": patient[4],
        "email": patient[5],
        "address": patient[6],
        "registration_date": patient[7],
    }
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        date_of_birth = request.POST.get("date_of_birth")
        gender = request.POST.get("gender")
        phone_number = request.POST.get("phone_number")
        email = request.POST.get("email")
        address = request.POST.get("address")
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE patients 
                SET first_name=%s, last_name=%s, date_of_birth=%s, gender=%s, 
                    phone_number=%s, email=%s, address=%s
                WHERE patient_id=%s
            """, [first_name, last_name, date_of_birth, gender, phone_number, email, address, patient_id])
        messages.success(request, "Patient details updated successfully!")
        return redirect('patient_details_admin', patient_id=patient_id)
    return render(request, "update_patient.html", {"patient": patient_data})

def staff_profile_admin(request, staff_id):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT s.staff_id, s.name, s.role, d.department_name, s.contact_info, 
                   s.hire_date, s.shift, s.status FROM staffs s 
                   LEFT JOIN departments d ON s.department_id = d.department_id 
                   WHERE s.staff_id = %s """, [staff_id])
        staff = cursor.fetchone()
    if not staff:
        messages.error(request, "Staff not found.")
        return redirect('staffs_list')
    staff_data = {
        "staff_id": staff[0],
        "staff_name": staff[1],
        "role": staff[2] if staff[2] else "N/A",
        "department": staff[3] if staff[3] else "N/A",
        "contact_info": staff[4] if staff[4] else "N/A",
        "hire_date": staff[5],
        "shift": staff[6],
        "status": staff[7],
    }
    return render(request, "staff_profile_admin.html", staff_data)

def log_action(user_id, action):
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO system_logs (log_time, action, user_id) VALUES (%s, %s, %s)",
            [datetime.now(), action, user_id]
        )

def departments_list(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    search_query = request.GET.get("search", "").strip()
    with connection.cursor() as cursor:
        if search_query:
            cursor.execute(
                "SELECT department_id, department_name FROM departments "
                "WHERE department_id LIKE %s OR department_name LIKE %s "
                "ORDER BY department_name ASC",
                [f"%{search_query}%", f"%{search_query}%"]
            )
        else:
            cursor.execute("SELECT department_id, department_name FROM departments ORDER BY department_name ASC")
        departments = cursor.fetchall()
    return render(request, "departments.html", {"departments": departments, "search_query": search_query})

def department_doctors(request, department_id):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    with connection.cursor() as cursor:
        cursor.execute("SELECT department_name FROM departments WHERE department_id = %s", [department_id])
        department = cursor.fetchone()
        if not department:
            return HttpResponse("Department not found", status=404)
        department_name = department[0]
        cursor.execute("""
            SELECT doctor_id, name, specialty 
            FROM doctors 
            WHERE department_id = %s
            ORDER BY name ASC
        """, [department_id])
        doctors = cursor.fetchall()
    return render(request, "department_doctors.html", {
        "department_name": department_name,
        "doctors": doctors
    })

def doctor_dashboard(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    doctor_id = request.session.get('doctor_id')
    if not doctor_id:
        return redirect('login')
    today = date.today()
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT a.appointment_id, a.patient_id, 
                   p.first_name, p.last_name,
                   a.appointment_time, a.notes as reason, a.status
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE a.doctor_id = %s 
            AND a.appointment_date = %s
            ORDER BY a.appointment_time
        """, [doctor_id, today])
        columns = [col[0] for col in cursor.description]
        appointments = [dict(zip(columns, row)) for row in cursor.fetchall()]
    context = {
        "doctor_name": request.session.get('doctor_name', 'Doctor'),
        "specialty": request.session.get('specialty', 'Unknown'),
        "department": request.session.get('department', 'Unknown'),
        "contact_info": request.session.get('contact_info', 'N/A'),
        "shift": request.session.get('shift', 'N/A'),
        "appointments": appointments,
        "today_appointments_count": len(appointments),
    }
    return render(request, "doctors.html", context)

def doctor_details_self(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    doctor_id = request.session.get('doctor_id')
    if not doctor_id:
        messages.error(request, "Doctor ID not found in session.")
        return redirect('doctor_home')
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT name, specialty, department_id, contact_info, shift, status FROM doctors WHERE doctor_id = %s",
            [doctor_id])
        doctor = cursor.fetchone()
    if not doctor:
        messages.error(request, "Doctor not found.")
        return redirect('doctor_home')
    doctor_data = {
        "doctor_id": doctor_id,
        "doctor_name": doctor[0],
        "specialty": doctor[1],
        "department_id": doctor[2],
        "contact_info": doctor[3],
        "shift": doctor[4],
        "status": doctor[5],
    }
    return render(request, "doctors_profile.html", doctor_data)

def doctors_list(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    search_query = request.GET.get("search", "").strip()
    with connection.cursor() as cursor:
        if search_query:
            cursor.execute(
                "SELECT doctor_id, name, specialty FROM doctors "
                "WHERE doctor_id LIKE %s OR name LIKE %s OR specialty LIKE %s "
                "ORDER BY name ASC",
                [f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"]
            )
        else:
            cursor.execute("SELECT doctor_id, name, specialty FROM doctors ORDER BY name ASC")
        doctors = cursor.fetchall()
    return render(request, "doctors_list.html", {"doctors": doctors, "search_query": search_query})

def patient_details(request, patient_id):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM patients WHERE patient_id = %s", [patient_id])
        patient = cursor.fetchone()
    if not patient:
        messages.error(request, "Patient not found.")
        return redirect('patient_list')
    patient_data = {
        "patient_id": patient[0],
        "first_name": patient[1],
        "last_name": patient[2],
        "date_of_birth": patient[3],
        "gender": patient[4],
        "phone_number": patient[5],
        "email": patient[6],
        "address": patient[7],
        "registration_date": patient[8],
    }
    return render(request, "patient_details.html", patient_data)

def op_visit(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    return render(request, 'op_visit.html')

def patient_list(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    search_query = request.GET.get("search", "").strip()
    with connection.cursor() as cursor:
        if search_query:
            cursor.execute(
                "SELECT patient_id, first_name, last_name, date_of_birth FROM patients "
                "WHERE patient_id LIKE %s OR first_name LIKE %s OR last_name LIKE %s"
                "ORDER BY first_name ASC",
                [f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"]
            )
        else:
            cursor.execute("SELECT patient_id, first_name, last_name FROM patients ORDER BY first_name ASC")
        patients = cursor.fetchall()
    return render(request, "patients.html", {"patients": patients, "search_query": search_query})

def staffs_list(request):
    search_query = request.GET.get("search", "").strip()
    with connection.cursor() as cursor:
        if search_query:
            cursor.execute(
                "SELECT staff_id, name, role FROM staffs "
                "WHERE staff_id LIKE %s OR name LIKE %s OR role LIKE %s "
                "ORDER BY name ASC",
                [f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"]
            )
        else:
            cursor.execute("SELECT staff_id, name, role FROM staffs ORDER BY name ASC")
        staffs = cursor.fetchall()
    return render(request, "staffs_list.html", {"staffs": staffs, "search_query": search_query})

def medicines_list(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    user_type = request.session.get('user_type', 'admin')
    home_url = 'accountant_home' if user_type == 'accountant' else 'admin_page'
    search_query = request.GET.get('q', '').strip()
    with connection.cursor() as cursor:
        if search_query:
            cursor.execute(
                "SELECT medicine_id, name, dosage, quantity FROM medicines WHERE medicine_id LIKE %s OR name LIKE %s",
                [f"%{search_query}%", f"%{search_query}%"]
            )
        else:
            cursor.execute("SELECT medicine_id, name, dosage, quantity FROM medicines")
        medicines = cursor.fetchall()
    return render(request, "medicines.html", {
        "medicines": medicines,
        "search_query": search_query,
        "home_url": home_url,
        "user_type": user_type
    })

def medicine_details(request, medicine_id):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    try:
        user_type = request.GET.get('user_type') or request.session.get('user_type', 'admin')
        home_url = 'accountant_home' if user_type == 'accountant' else 'admin_page'
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT medicine_id, name, manufacturer, dosage, quantity, price
                FROM medicines 
                WHERE medicine_id = %s
            """, [medicine_id])
            if cursor.rowcount == 0:
                messages.error(request, "Medicine not found")
                return redirect('medicines_list')
            columns = [col[0] for col in cursor.description]
            medicine = dict(zip(columns, cursor.fetchone()))
            back_url = reverse('medicines_list') + f"?user_type={user_type}"
            return render(request, 'medicine_detail.html', {
                'medicine': medicine,
                'user_type': user_type,
                'home_url': home_url,
                'back_url': back_url
            })
    except Exception as e:
        messages.error(request, f"Error retrieving medicine details: {str(e)}")
        return redirect('medicines_list')

def create_prescription(request, appointment_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT * FROM appointments 
            WHERE appointment_id = %s
        """, [appointment_id])
        appointment = dict(zip([col[0] for col in cursor.description], cursor.fetchone()))
        cursor.execute("""
            SELECT * FROM patients 
            WHERE patient_id = %s
        """, [appointment['patient_id']])
        patient = dict(zip([col[0] for col in cursor.description], cursor.fetchone()))
        cursor.execute("""
            SELECT * FROM doctors 
            WHERE doctor_id = %s
        """, [appointment['doctor_id']])
        doctor = dict(zip([col[0] for col in cursor.description], cursor.fetchone()))
    if request.method == 'POST':
        medicine_id = request.POST.get('medicine')
        dosage = request.POST.get('dosage')
        morning = request.POST.get('morning', '0')
        noon = request.POST.get('noon', '0')
        evening = request.POST.get('evening', '0')
        night = request.POST.get('night', '0')
        notes = request.POST.get('notes', '')
        intake_schedule = f"{morning}-{noon}-{evening}-{night}"
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO prescriptions (
                    patient_id, 
                    doctor_id, 
                    medicine_id, 
                    dosage_instructions, 
                    intake_schedule, 
                    notes,
                    prescription_date,
                    appointment_id
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
                RETURNING prescription_id
            """, [
                appointment['patient_id'],
                appointment['doctor_id'],
                medicine_id,
                dosage,
                intake_schedule,
                notes,
                appointment_id
            ])
            prescription_id = cursor.fetchone()[0]
            cursor.execute("""
                UPDATE appointments 
                SET status = 'Completed' 
                WHERE appointment_id = %s
            """, [appointment_id])
        return redirect('view_prescription', prescription_id=prescription_id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM medicines")
        medicines = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    context = {
        'patient': patient,
        'appointment': appointment,
        'medicines': medicines
    }
    return render(request, 'prescription_form.html', context)

def view_prescription(request, prescription_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT p.*, m.name as medicine_name, m.manufacturer,
                   pat.first_name as patient_first, pat.last_name as patient_last,
                   d.name as doctor_name, d.department
            FROM prescriptions p
            JOIN medicines m ON p.medicine_id = m.medicine_id
            JOIN patients pat ON p.patient_id = pat.patient_id
            JOIN doctors d ON p.doctor_id = d.doctor_id
            WHERE p.prescription_id = %s
        """, [prescription_id])
        prescription = dict(zip([col[0] for col in cursor.description], cursor.fetchone()))
        frequency = prescription['intake_schedule'].split('-')
        prescription['frequency'] = frequency
    context = {
        'prescription': prescription,
        'patient': {
            'patient_id': prescription['patient_id'],
            'first_name': prescription['patient_first'],
            'last_name': prescription['patient_last']
        },
        'doctor': {
            'name': prescription['doctor_name'],
            'department': prescription['department']
        },
        'medicines': [{
            'name': prescription['medicine_name'],
            'manufacturer': prescription['manufacturer'],
            'dosage': prescription['dosage_instructions'],
            'frequency': frequency,
            'notes': prescription['notes']
        }]
    }
    return render(request, 'prescriptions.html', context)

def remove_appointment(request, appointment_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE appointments 
            SET status = 'Cancelled' 
            WHERE appointment_id = %s
        """, [appointment_id])
    return redirect('doctor_dashboard')


def nurse_home(request):
    # Authentication check
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    if not request.session.get('staff_id') or request.session.get('role') != 'Nurse':
        messages.error(request, "Please login as nurse to access this page")
        return redirect('login')

    staff_id = request.session.get('staff_id')
    today = date.today()

    # Handle POST request (form submission)
    if request.method == "POST":
        duty_description = request.POST.get('duty_description')
        shift = request.session.get('shift', 'Morning')

        try:
            with connection.cursor() as cursor:
                # Generate a unique duty_id using UUID
                duty_id = f"DUTY{uuid.uuid4().hex[:6].upper()}"

                # Insert the new duty
                cursor.execute(
                    """INSERT INTO nurse_duties 
                    (duty_id, staff_id, duty_description, duty_date, shift) 
                    VALUES (%s, %s, %s, %s, %s)""",
                    [duty_id, staff_id, duty_description, today, shift]
                )

                # Verify the insertion
                cursor.execute(
                    """SELECT COUNT(*) FROM nurse_duties 
                    WHERE duty_id = %s AND staff_id = %s""",
                    [duty_id, staff_id]
                )
                if cursor.fetchone()[0] == 0:
                    raise Exception("Duty not inserted successfully")

            messages.success(request, "Duty logged successfully!")
        except Exception as e:
            messages.error(request, f"Failed to log duty: {str(e)}")
            print(f"Error inserting duty: {str(e)}")  # Log the error for debugging

        return redirect('nurse_home')

    # Handle GET request
    duties = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT duty_id, duty_description, shift, duty_date 
                FROM nurse_duties 
                WHERE staff_id = %s AND duty_date = %s
                ORDER BY duty_date DESC, duty_id DESC""",
                [staff_id, today]
            )
            columns = [col[0] for col in cursor.description]
            duties = [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        messages.error(request, f"Error loading duties: {str(e)}")
        print(f"Error loading duties: {str(e)}")  # Log the error for debugging

    return render(request, 'nurse.html', {
        'duties': duties,
        'staff_name': request.session.get('staff_name', '')
    })

def log_duty(request):
    if request.method == "POST":
        staff_id = request.session.get('staff_id')
        duty_description = request.POST.get("duty_description")
        shift = request.session.get('shift')
        print("staff_id:", request.session.get('staff_id'))
        print("shift:", request.session.get('shift'))

        if not staff_id or not shift:
            messages.error(request, "Session expired. Please log in again.")
            return redirect('login')
        duty_id = f"DUTY{uuid.uuid4().hex[:6].upper()}"
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO nurse_duties (duty_id, staff_id, duty_description, shift) 
                VALUES (%s, %s, %s, %s)
            """, [duty_id, staff_id, duty_description, shift])
        messages.success(request, "Duty logged successfully!")
        return redirect('nurse_home')
    return redirect('nurse_home')

def view_duty_logs(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    search_query = request.GET.get('search', '')
    with connection.cursor() as cursor:
        if search_query:
            cursor.execute("""
                SELECT duty_id, staff_id, duty_description, duty_date, shift 
                FROM nurse_duties
                WHERE duty_id LIKE %s OR staff_id LIKE %s
                ORDER BY duty_date DESC
            """, [f'%{search_query}%', f'%{search_query}%'])
        else:
            cursor.execute("""
                SELECT duty_id, staff_id, duty_description, duty_date, shift 
                FROM nurse_duties 
                ORDER BY duty_date DESC
            """)
        nurse_duties = cursor.fetchall()
    return render(request, 'duty_logs_list.html', {
        'nurse_duties': nurse_duties,
        'search_query': search_query
    })

def duty_details(request, duty_id):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    d.duty_id, d.staff_id, d.duty_description, 
                    d.shift, d.duty_date,
                    s.name, s.role, s.department_id, s.contact_info, 
                    s.hire_date, s.status
                FROM nurse_duties d
                JOIN staffs s ON d.staff_id = s.staff_id
                WHERE d.duty_id = %s
            """, [duty_id])
            if cursor.rowcount == 0:
                messages.error(request, "Duty log not found")
                return redirect('view_duty_logs')
            columns = [col[0] for col in cursor.description]
            duty = dict(zip(columns, cursor.fetchone()))
            if duty.get('department_id'):
                with connection.cursor() as dept_cursor:
                    dept_cursor.execute("""
                        SELECT department_name FROM departments 
                        WHERE department_id = %s
                    """, [duty['department_id']])
                    dept_result = dept_cursor.fetchone()
                    duty['department_name'] = dept_result[0] if dept_result else "Not assigned"
            else:
                duty['department_name'] = "Not assigned"
        return render(request, 'duty_details.html', {'duty': duty})
    except Exception as e:
        messages.error(request, f"Error retrieving duty details: {str(e)}")
        return redirect('view_duty_logs')

def accountant_home(request):
    if not request.session.get('is_logged_in'):
        return redirect('login')
    if 'staff_id' not in request.session or request.session.get('role') != 'Accountant':
        messages.error(request, "Unauthorized Access!")
        return redirect('login_view')
    return render(request, "accountant.html")

def staff_profile(request):
    if not request.session.get('is_logged_in'):
        messages.error(request, "Please log in to view your profile")
        return redirect('login')
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "Staff information not found")
        return redirect('login')
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT s.staff_id, s.name, s.role, d.department_name, 
                       s.department_id, s.contact_info, s.shift, s.status, s.hire_date
                FROM staffs s
                LEFT JOIN departments d ON s.department_id = d.department_id
                WHERE s.staff_id = %s
            """, [staff_id])
            staff = cursor.fetchone()
        if not staff:
            messages.error(request, "Staff profile not found")
            return redirect('login')
        context = {
            'staff_id': staff[0],
            'staff_name': staff[1],
            'role': staff[2],
            'department': staff[3],
            'department_id': staff[4],
            'contact_info': staff[5],
            'shift': staff[6],
            'status': staff[7],
            'hire_date': staff[8],
            'request': request
        }
    except Exception as e:
        messages.error(request, f"Error accessing profile: {str(e)}")
        return redirect('login')
    return render(request, "staff_profile.html", context)

def patient_registration(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    with connection.cursor() as cursor:
        cursor.execute("SELECT MAX(patient_id) FROM patients")
        last_id = cursor.fetchone()[0]
        if last_id:
            prefix = last_id[:1]
            num = int(last_id[1:]) + 1
            new_patient_id = f"{prefix}{num:06d}"
        else:
            new_patient_id = "P000201"
    if request.method == 'POST':
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO patients (
                        patient_id, first_name, last_name, date_of_birth,
                        gender, phone_number, email, address, registration_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [
                    new_patient_id,
                    request.POST.get('first_name'),
                    request.POST.get('last_name'),
                    request.POST.get('date_of_birth'),
                    request.POST.get('gender'),
                    request.POST.get('phone_number'),
                    request.POST.get('email'),
                                        request.POST.get('address'),
                    timezone.now().date()
                ])
            messages.success(request, f"Patient {new_patient_id} registered successfully!")
            return redirect('accountant_home')
        except Exception as e:
            messages.error(request, f"Error registering patient: {str(e)}")
    return render(request, 'new_patient.html', {
        'new_patient_id': new_patient_id,
        'today': timezone.now().date()
    })

def booking(request):
    if not request.session.get('is_logged_in', False):
        return redirect('login')
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        doctor_id = request.POST.get('doctor_id')
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')
        notes = request.POST.get('notes', '')
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT patient_id FROM patients WHERE patient_id = %s", [patient_id])
                if not cursor.fetchone():
                    messages.error(request, "Patient ID not found")
                    return redirect('booking')
                cursor.execute("SELECT name FROM doctors WHERE doctor_id = %s", [doctor_id])
                doctor = cursor.fetchone()
                if not doctor:
                    messages.error(request, "Doctor not found")
                    return redirect('booking')
                cursor.execute("""
                    SELECT appointment_id FROM appointments 
                    WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s
                    LIMIT 1
                """, [doctor_id, appointment_date, appointment_time])
                if cursor.fetchone():
                    messages.warning(request, "Doctor already has an appointment at this time")
                    return redirect('booking')
                cursor.execute("""
                    INSERT INTO appointments 
                    (patient_id, doctor_id, appointment_date, appointment_time, notes)
                    VALUES (%s, %s, %s, %s, %s)
                """, [patient_id, doctor_id, appointment_date, appointment_time, notes])
                messages.success(request,
                    f"Appointment booked with Dr. {doctor[0]} on {appointment_date} at {appointment_time}")
                return redirect('appointments_list')
        except Exception as e:
            messages.error(request, f"Error booking appointment: {str(e)}")
            return redirect('booking')
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT doctor_id, name, specialty FROM doctors 
            WHERE status = 'active' 
            ORDER BY name
        """)
        columns = [col[0] for col in cursor.description]
        doctors = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return render(request, 'booking.html', {
        'doctors': doctors,
        'today': timezone.now().date()
    })

def appointments_list(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT a.appointment_id, 
                   p.patient_id, p.first_name AS patient_first_name, p.last_name AS patient_last_name,
                   d.doctor_id, d.name AS doctor_name,
                   a.appointment_date, a.appointment_time, a.status
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            JOIN doctors d ON a.doctor_id = d.doctor_id
            ORDER BY a.appointment_date ASC, a.appointment_time ASC
        """)
        columns = [col[0] for col in cursor.description]
        appointments = []
        for row in cursor.fetchall():
            appointment = dict(zip(columns, row))
            appointment['patient'] = {
                'first_name': appointment.pop('patient_first_name'),
                'last_name': appointment.pop('patient_last_name')
            }
            appointment['doctor'] = {
                'name': appointment.pop('doctor_name')
            }
            appointments.append(appointment)
    return render(request, 'appointments.html', {'appointments': appointments})

def calculate_medicine_price(request):
    if request.method == 'GET':
        medicine_id = request.GET.get('medicine_id')
        quantity = int(request.GET.get('quantity', 0))
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT price, quantity FROM medicines 
                    WHERE medicine_id = %s
                """, [medicine_id])
                result = cursor.fetchone()
                if not result:
                    return JsonResponse({'error': 'Medicine not found'}, status=404)
                price, stock = result
                if quantity > stock:
                    return JsonResponse({'error': 'Insufficient stock'}, status=400)
                subtotal = price * quantity
                tax = subtotal * 0.05
                total = subtotal + tax
                return JsonResponse({
                    'unit_price': float(price),
                    'subtotal': float(subtotal),
                    'tax': float(tax),
                    'total': float(total),
                    'stock': stock
                })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)

def generate_bill(request):
    if not request.session.get('is_logged_in'):
        messages.error(request, "You must be logged in to generate bills")
        return redirect('login')
    if request.method == 'POST':
        try:
            patient_id = request.POST.get('patient_id')
            if not patient_id:
                raise ValueError("Patient ID is required")
            staff_id = request.session.get('staff_id')
            if not staff_id:
                raise ValueError("Staff session invalid")
            payment_method = request.POST.get('payment_method')
            if not payment_method:
                raise ValueError("Payment method is required")
            payment_status = request.POST.get('payment_status', 'unpaid')
            prescription_id = request.POST.get('prescription_id')
            if not prescription_id:
                raise ValueError("Prescription ID is required")
            if not prescription_id.isdigit():
                raise ValueError("Invalid Prescription ID format")
            medicine_ids = request.POST.getlist('selected_medicines')
            if not medicine_ids:
                raise ValueError("No medicines selected")
            quantities = []
            prices = []
            for med_id in medicine_ids:
                qty = request.POST.get(f'quantity_{med_id}') or request.POST.get('quantity')
                if not qty or not qty.isdigit():
                    raise ValueError(f"Invalid quantity for medicine {med_id}")
                qty_int = int(qty)
                if qty_int < 1:
                    raise ValueError(f"Quantity must be at least 1 for medicine {med_id}")
                quantities.append(qty_int)
                price = request.POST.get(f'medicine_{med_id}_price')
                if not price:
                    raise ValueError(f"Price missing for medicine {med_id}")
                prices.append(Decimal(price))
            with transaction.atomic():
                bill_id = f"BILL-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT p.first_name, p.last_name, 
                               d.doctor_id, d.name as doctor_name
                        FROM patients p
                        JOIN prescriptions pr ON p.patient_id = pr.patient_id
                        JOIN doctors d ON pr.doctor_id = d.doctor_id
                        WHERE p.patient_id = %s AND pr.prescription_id = %s
                        LIMIT 1
                    """, [patient_id, prescription_id])
                    result = cursor.fetchone()
                    if not result:
                        raise ValueError("Patient or prescription not found or doesn't match")
                    patient_data = dict(zip([col[0] for col in cursor.description], result))
                    subtotal = Decimal(0)
                    for med_id, qty, price in zip(medicine_ids, quantities, prices):
                        subtotal += price * qty
                    tax = subtotal * Decimal('0.05')
                    grand_total = subtotal + tax
                    cursor.execute("""
                        INSERT INTO billing (
                            bill_id, patient_id, doctor_id, prescription_id,
                            subtotal, tax_amount, grand_total, 
                            payment_method, payment_status, created_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, [
                        bill_id, patient_id, patient_data['doctor_id'], prescription_id,
                        float(subtotal), float(tax), float(grand_total),
                        payment_method, payment_status, staff_id
                    ])
                    for med_id, qty in zip(medicine_ids, quantities):
                        cursor.execute("""
                            SELECT name, price, quantity 
                            FROM medicines 
                            WHERE medicine_id = %s FOR UPDATE
                        """, [med_id])
                        med_data = cursor.fetchone()
                        if not med_data:
                            raise ValueError(f"Medicine {med_id} not found")
                        med_name, price, stock = med_data
                        if qty > stock:
                            raise ValueError(f"Insufficient stock for {med_name}. Available: {stock}, Requested: {qty}")
                        total_price = Decimal(price) * qty
                        cursor.execute("""
                            INSERT INTO billing_items (
                                bill_id, medicine_id, quantity, unit_price, total_price
                            ) VALUES (%s, %s, %s, %s, %s)
                        """, [bill_id, med_id, qty, float(price), float(total_price)])
                        cursor.execute("""
                            UPDATE medicines 
                            SET quantity = quantity - %s 
                            WHERE medicine_id = %s
                        """, [qty, med_id])
                    cursor.execute("SELECT COUNT(*) FROM billing WHERE bill_id = %s", [bill_id])
                    if cursor.fetchone()[0] != 1:
                        raise ValueError("Bill header not created")
                    cursor.execute("SELECT COUNT(*) FROM billing_items WHERE bill_id = %s", [bill_id])
                    if cursor.fetchone()[0] != len(medicine_ids):
                        raise ValueError("Not all bill items were created")
                messages.success(request, f"Bill {bill_id} generated successfully!")
                return redirect('view_bill', bill_id=bill_id)
        except Exception as e:
            error_msg = f"Bill generation failed: {str(e)}"
            messages.error(request, error_msg)
            logger.error(error_msg, exc_info=True)
            return redirect('patient_prescriptions_billing', patient_id=patient_id)
    messages.error(request, "Invalid request method")
    return redirect('accountant_home')

def view_bill(request, bill_id):
    if not request.session.get('is_logged_in'):
        return redirect('login')
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT b.bill_id, b.billing_date, b.subtotal, 
                       b.tax_amount, b.grand_total, b.payment_method, 
                       b.payment_status, p.patient_id, p.first_name, 
                       p.last_name, d.name as doctor_name, 
                       b.prescription_id
                FROM billing b
                JOIN patients p ON b.patient_id = p.patient_id
                JOIN doctors d ON b.doctor_id = d.doctor_id
                WHERE b.bill_id = %s
            """, [bill_id])
            bill = dict(zip([col[0] for col in cursor.description], cursor.fetchone()))
            cursor.execute("""
                SELECT bi.medicine_id, m.name as medicine_name, 
                       bi.unit_price, bi.quantity, bi.total_price
                FROM billing_items bi
                JOIN medicines m ON bi.medicine_id = m.medicine_id
                WHERE bi.bill_id = %s
            """, [bill_id])
            items = [dict(zip([col[0] for col in cursor.description], row))
                     for row in cursor.fetchall()]
        return render(request, 'bill_view.html', {
            'bill': bill,
            'items': items
        })
    except Exception as e:
        messages.error(request, f"Error viewing bill: {str(e)}")
        return redirect('accountant_home')

def patient_list_for_billing(request):
    if not request.session.get('is_logged_in'):
        return redirect('login')
    search_query = request.GET.get('search', '')
    try:
        with connection.cursor() as cursor:
            if search_query:
                cursor.execute("""
                    SELECT DISTINCT p.patient_id, 
                           CONCAT(pt.first_name, ' ', pt.last_name) AS patient_name
                    FROM prescriptions p
                    JOIN patients pt ON p.patient_id = pt.patient_id
                    WHERE p.patient_id LIKE %s 
                       OR pt.first_name LIKE %s 
                       OR pt.last_name LIKE %s
                    ORDER BY patient_name
                """, [f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
            else:
                cursor.execute("""
                    SELECT DISTINCT p.patient_id, 
                           CONCAT(pt.first_name, ' ', pt.last_name) AS patient_name
                    FROM prescriptions p
                    JOIN patients pt ON p.patient_id = pt.patient_id
                    ORDER BY patient_name
                """)
            patients = [dict(zip([col[0] for col in cursor.description], row))
                       for row in cursor.fetchall()]
        return render(request, 'patient_billing_list.html', {
            'patients': patients,
            'search_query': search_query
        })
    except Exception as e:
        messages.error(request, f"Error loading patients: {str(e)}")
        return redirect('accountant_home')

def patient_prescriptions_billing(request, patient_id):
    if not request.session.get('is_logged_in'):
        return redirect('login')
    if request.method == 'POST' and 'update_quantity' in request.POST:
        medicine_id = request.POST.get('medicine_id')
        new_quantity = int(request.POST.get('quantity', 1))
        if 'medicine_quantities' not in request.session:
            request.session['medicine_quantities'] = {}
        request.session['medicine_quantities'][medicine_id] = new_quantity
        request.session.modified = True
        return redirect('patient_prescriptions_billing', patient_id=patient_id)
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT patient_id, CONCAT(first_name, ' ', last_name) AS patient_name
                FROM patients WHERE patient_id = %s
            """, [patient_id])
            patient_row = cursor.fetchone()
            if not patient_row:
                messages.error(request, "Patient not found")
                return redirect('patient_billing_list')
            patient = dict(zip(['patient_id', 'patient_name'], patient_row))
            cursor.execute("""
                SELECT p.prescription_id, p.prescription_date, 
                       d.name AS doctor_name, p.doctor_id, p.medicine_id
                FROM prescriptions p
                JOIN doctors d ON p.doctor_id = d.doctor_id
                WHERE p.patient_id = %s
                ORDER BY p.prescription_date DESC
            """, [patient_id])
            prescriptions = [dict(zip([col[0] for col in cursor.description], row))
                             for row in cursor.fetchall()]
            if prescriptions:
                medicine_ids = [str(p['medicine_id']) for p in prescriptions if p['medicine_id']]
                cursor.execute(f"""
                    SELECT m.medicine_id, m.name, m.dosage, m.price, m.quantity as stock,
                           p.dosage_instructions, p.intake_schedule, 
                           p.prescription_id, p.prescription_date,
                           d.name AS doctor_name
                    FROM medicines m
                    JOIN prescriptions p ON m.medicine_id = p.medicine_id
                    JOIN doctors d ON p.doctor_id = d.doctor_id
                    WHERE p.patient_id = %s AND p.medicine_id IN ({','.join(['%s'] * len(medicine_ids))})
                    ORDER BY p.prescription_date DESC
                """, [patient_id] + medicine_ids)
                prescribed_meds = [dict(zip([col[0] for col in cursor.description], row))
                                   for row in cursor.fetchall()]
                subtotal = 0
                tax_rate = 0.05
                for med in prescribed_meds:
                    quantity = request.session.get('medicine_quantities', {}).get(str(med['medicine_id']), 1)
                    med['current_quantity'] = quantity
                    med['item_total'] = float(med['price']) * quantity
                    subtotal += med['item_total']
                tax = subtotal * tax_rate
                grand_total = subtotal + tax
            else:
                prescribed_meds = []
                subtotal = 0
                tax = 0
                grand_total = 0
                messages.info(request, "No prescriptions found for this patient")
        return render(request, 'patient_prescriptions_billing.html', {
            'patient': patient,
            'prescriptions': prescriptions,
            'prescribed_meds': prescribed_meds,
            'subtotal': subtotal,
            'tax': tax,
            'grand_total': grand_total
        })
    except Exception as e:
        messages.error(request, f"Error loading patient prescriptions: {str(e)}")
        return redirect('patient_billing_list')