from django.contrib import admin
from .models import (
    Admin, Appointment, Billing, BillingItem, Department, Doctor,
    Medicine, NurseDuty, Patient, Prescription, PrescriptionItem,
    Staff, SystemLog
)


@admin.register(Admin)
class AdminAdmin(admin.ModelAdmin):
    list_display = ('admin_id', 'username', 'email', 'status', 'created_at')
    search_fields = ('admin_id', 'username', 'email', 'contact_info')
    list_filter = ('status',)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('appointment_id', 'patient', 'doctor', 'appointment_date', 'appointment_time', 'status')
    search_fields = ('appointment_id', 'patient__first_name', 'doctor__name')
    list_filter = ('status', 'appointment_date')


@admin.register(Billing)
class BillingAdmin(admin.ModelAdmin):
    list_display = ('bill_id', 'patient', 'doctor', 'billing_date', 'grand_total', 'payment_status')
    search_fields = ('bill_id', 'patient__first_name', 'doctor__name')
    list_filter = ('payment_status', 'billing_date')


@admin.register(BillingItem)
class BillingItemAdmin(admin.ModelAdmin):
    list_display = ('item_id', 'bill', 'medicine', 'quantity', 'total_price')
    search_fields = ('bill__bill_id', 'medicine__name')
    list_filter = ('medicine',)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('department_id', 'department_name')
    search_fields = ('department_id', 'department_name')


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('doctor_id', 'name', 'specialty', 'department', 'status')
    search_fields = ('doctor_id', 'name', 'license_number')
    list_filter = ('status', 'specialty')


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('medicine_id', 'name', 'manufacturer', 'dosage', 'quantity', 'price')
    search_fields = ('name', 'manufacturer')
    list_filter = ('manufacturer',)


@admin.register(NurseDuty)
class NurseDutyAdmin(admin.ModelAdmin):
    list_display = ('duty_id', 'staff', 'duty_date', 'shift')
    search_fields = ('duty_id', 'staff__name', 'duty_description')
    list_filter = ('shift', 'duty_date')


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('patient_id', 'first_name', 'last_name', 'gender', 'phone_number', 'registration_date')
    search_fields = ('patient_id', 'first_name', 'last_name', 'email', 'phone_number')
    list_filter = ('gender', 'registration_date')


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('prescription_id', 'patient', 'doctor', 'prescription_date')
    search_fields = ('prescription_id', 'patient__first_name', 'doctor__name', 'medicine__name')
    list_filter = ('prescription_date',)


@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
    list_display = ('item_id', 'prescription', 'medicine', 'dosage_instructions')
    search_fields = ('prescription__prescription_id', 'medicine__name')


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('staff_id', 'name', 'role', 'status')
    search_fields = ('staff_id', 'name', 'role')
    list_filter = ('status', 'role')


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ('slog_id', 'log_time', 'action', 'user_id')
    search_fields = ('action', 'user_id')
    list_filter = ('log_time',)

    def has_delete_permission(self, request, obj=None):
        return False  # Prevent deletion

    def has_add_permission(self, request):
        return False  # Optional: prevent adding new logs manually

    readonly_fields = [field.name for field in SystemLog._meta.fields]  # Make all fields read-only
