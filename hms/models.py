from django.db import models

class Admin(models.Model):
    admin_id = models.CharField(max_length=7, primary_key=True)
    username = models.CharField(max_length=255, unique=True)
    password = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    contact_info = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admins'

    def __str__(self):
        return self.username

class Appointment(models.Model):
    appointment_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    doctor = models.ForeignKey('Doctor', on_delete=models.CASCADE)
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=[('Scheduled', 'Scheduled'), ('Completed', 'Completed'), ('Cancelled', 'Cancelled')],
        default='Scheduled',
        null=True
    )
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'appointments'

    def __str__(self):
        return f"Appointment {self.appointment_id}"

class Billing(models.Model):
    bill_id = models.CharField(max_length=30, primary_key=True)
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    doctor = models.ForeignKey('Doctor', on_delete=models.CASCADE)
    prescription = models.ForeignKey('Prescription', on_delete=models.CASCADE)
    billing_date = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=10, choices=[('paid', 'Paid'), ('unpaid', 'Unpaid')], default='unpaid', null=True)
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    created_by = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, db_column='created_by')

    class Meta:
        db_table = 'billing'

    def __str__(self):
        return self.bill_id

class BillingItem(models.Model):
    item_id = models.AutoField(primary_key=True)
    bill = models.ForeignKey(Billing, on_delete=models.SET_NULL, null=True)
    medicine = models.ForeignKey('Medicine', on_delete=models.CASCADE)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'billing_items'

    def __str__(self):
        return f"{self.medicine.name} x {self.quantity}"

class Department(models.Model):
    department_id = models.CharField(max_length=10, primary_key=True)
    department_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'departments'

    def __str__(self):
        return self.department_name

class Doctor(models.Model):
    doctor_id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255)
    specialty = models.CharField(max_length=255)
    license_number = models.CharField(max_length=255, unique=True)
    contact_info = models.CharField(max_length=255)
    hire_date = models.DateField()
    shift = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, db_column='department_id')

    class Meta:
        managed = False
        db_table = 'doctors'

    def __str__(self):
        return self.name

class Medicine(models.Model):
    medicine_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    manufacturer = models.CharField(max_length=255)
    dosage = models.CharField(max_length=50)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'medicines'

    def __str__(self):
        return self.name

class NurseDuty(models.Model):
    SHIFT_CHOICES = [
        ('Morning', 'Morning'),
        ('Evening', 'Evening'),
        ('Night', 'Night'),
    ]

    duty_id = models.CharField(max_length=10, primary_key=True)
    staff = models.ForeignKey('Staff', on_delete=models.CASCADE)
    duty_description = models.TextField()
    duty_date = models.DateField(auto_now_add=True)
    shift = models.CharField(max_length=10, choices=SHIFT_CHOICES)

    class Meta:
        db_table = 'nurse_duties'

    def __str__(self):
        return self.duty_id

class Patient(models.Model):
    patient_id = models.CharField(max_length=7, primary_key=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField()
    address = models.CharField(max_length=255)
    registration_date = models.DateField()

    class Meta:
        db_table = 'patients'

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Prescription(models.Model):
    prescription_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    dosage_instructions = models.CharField(max_length=255)
    intake_schedule = models.CharField(max_length=7)
    notes = models.TextField(null=True, blank=True)
    prescription_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'prescriptions'

    def __str__(self):
        return f"Prescription {self.prescription_id}"

class PrescriptionItem(models.Model):
    item_id = models.AutoField(primary_key=True)
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE)
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    dosage_instructions = models.CharField(max_length=255)
    intake_schedule = models.CharField(max_length=50)

    class Meta:
        db_table = 'prescription_items'

    def __str__(self):
        return f"{self.medicine.name} ({self.prescription.prescription_id})"

class Staff(models.Model):
    staff_id = models.CharField(max_length=7, primary_key=True)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255)
    contact_info = models.CharField(max_length=255)
    status = models.CharField(max_length=50)

    class Meta:
        db_table = 'staffs'

    def __str__(self):
        return self.name

class SystemLog(models.Model):
    slog_id = models.BigAutoField(primary_key=True)
    log_time = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=255)
    user_id = models.CharField(max_length=30, null=True)

    class Meta:
        db_table = 'system_logs'

    def __str__(self):
        return f"{self.log_time.strftime('%Y-%m-%d %H:%M:%S')} - {self.action}"
