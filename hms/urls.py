from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),  # Login page (for all users)
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin-logout-redirect/', views.admin_logout_redirect_to_settings, name='admin_logout_redirect'),


    path('accountant/', views.accountant_home, name='accountant_home'),
    path('accountant/detail/', views.staff_profile, name='staff_profile'),
    path('accountant/appointments/', views.appointments_list, name='appointments_list'),
    path('accountant/booking/', views.booking, name='booking'),

    path('registration/', views.patient_registration, name='patient_registration'),


    path('admin_page/', views.admin, name='admin_page'),  # Admin Dashboard
    path('admin_page/settings/', views.admin_settings_page, name='admin_settings_page'), # Admin Dashboard Settings
    path('admin_page/view-logs/', views.view_logs, name='view_logs'),

    path('departments/', views.departments_list, name='departments_list'),
    path('departments/<str:department_id>/', views.department_doctors, name='department_doctors'),

    path('doctors/update/<str:doctor_id>/', views.update_doctor, name='update_doctor'),

    path('doctors/list/', views.doctors_list, name='doctors_list'),
    path('doctors/details/<str:doctor_id>/', views.doctor_profile_admin, name='doctor_profile_admin'),

    path('doctor/home/', views.doctor_dashboard, name='doctor_dashboard'),  # Doctor Dashboard
    path('doctor/op_visit/', views.op_visit, name='op_visit'),
    path('doctor/detail/', views.doctor_details_self, name='doctor_detail'),
    path('prescription/<int:appointment_id>/', views.create_prescription, name='create_prescription'),
    path('prescription/view/<int:prescription_id>/', views.view_prescription, name='view_prescription'),
    path('appointment/remove/<int:appointment_id>/', views.remove_appointment, name='remove_appointment'),



    path('medicines/', views.medicines_list, name='medicines_list'),
    path('medicines/<int:medicine_id>/', views.medicine_details, name='medicine_details'),

    path('nurse/', views.nurse_home, name='nurse_home'),
    path('nurse/detail/', views.staff_profile, name='staff_profile'),

    path('view_duty_logs/', views.view_duty_logs, name='view_duty_logs'),
    path('log_duty/', views.log_duty, name='log_duty'),
    path('duty/details/<str:duty_id>/', views.duty_details, name='duty_details'),

    path('patients/', views.patient_list, name='patient_list'),
    path('patients/details/<str:patient_id>/', views.patient_details, name='patient_details'),
    path('patients/update/<str:patient_id>/', views.update_patient, name='update_patient'),



    path('billing/patients/', views.patient_list_for_billing, name='patient_billing_list'),
    path('billing/patient/<str:patient_id>/', views.patient_prescriptions_billing,name='patient_prescriptions_billing'),
    path('billing/calculate-price/', views.calculate_medicine_price, name='calculate_medicine_price'),
    path('billing/generate/', views.generate_bill, name='generate_bill'),
    path('billing/view/<str:bill_id>/', views.view_bill, name='view_bill'),


    path('staffs/list/', views.staffs_list, name='staffs_list'),

    path('staffs/details/<str:staff_id>/', views.staff_profile_admin, name='staff_details_admin'),
    path('staffs/update/<str:staff_id>/', views.update_staff, name='update_staff'),



]
