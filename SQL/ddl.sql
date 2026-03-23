/*
Doctor Recommendation System - SQL Server DDL
Polyglot Persistence Assignment (RDBMS component)
*/

SET XACT_ABORT ON;
GO

/* ---------------------------
   Drop existing objects safely
---------------------------- */
DROP TABLE IF EXISTS dbo.Reviews;
DROP TABLE IF EXISTS dbo.Appointments;
DROP TABLE IF EXISTS dbo.Patient_Symptoms;
DROP TABLE IF EXISTS dbo.Symptom_Specialization;
DROP TABLE IF EXISTS dbo.Doctor_Specializations;
DROP TABLE IF EXISTS dbo.Doctors;
DROP TABLE IF EXISTS dbo.Symptoms;
DROP TABLE IF EXISTS dbo.Specializations;
DROP TABLE IF EXISTS dbo.Patients;
DROP TABLE IF EXISTS dbo.Clinics;
GO

/* ---------------------------
   Master entities
---------------------------- */
CREATE TABLE dbo.Patients (
    Patient_ID INT IDENTITY(1,1) NOT NULL,
    Full_Name NVARCHAR(120) NOT NULL,
    Gender CHAR(1) NULL,
    Date_Of_Birth DATE NULL,
    Phone VARCHAR(20) NULL,
    Email VARCHAR(120) NULL,
    Created_At DATETIME2(0) NOT NULL CONSTRAINT DF_Patients_CreatedAt DEFAULT SYSDATETIME(),
    CONSTRAINT PK_Patients PRIMARY KEY (Patient_ID),
    CONSTRAINT CK_Patients_Gender CHECK (Gender IN ('M', 'F', 'O')),
    CONSTRAINT UQ_Patients_Email UNIQUE (Email)
);
GO

CREATE TABLE dbo.Clinics (
    Clinic_ID INT IDENTITY(1,1) NOT NULL,
    Clinic_Name NVARCHAR(150) NOT NULL,
    City NVARCHAR(80) NULL,
    Address_Line NVARCHAR(255) NULL,
    CONSTRAINT PK_Clinics PRIMARY KEY (Clinic_ID),
    CONSTRAINT UQ_Clinics_ClinicName UNIQUE (Clinic_Name)
);
GO

CREATE TABLE dbo.Specializations (
    Specialization_ID INT IDENTITY(1,1) NOT NULL,
    Specialization_Name NVARCHAR(120) NOT NULL,
    CONSTRAINT PK_Specializations PRIMARY KEY (Specialization_ID),
    CONSTRAINT UQ_Specializations_Name UNIQUE (Specialization_Name)
);
GO

CREATE TABLE dbo.Symptoms (
    Symptom_ID INT IDENTITY(1,1) NOT NULL,
    Symptom_Name NVARCHAR(120) NOT NULL,
    CONSTRAINT PK_Symptoms PRIMARY KEY (Symptom_ID),
    CONSTRAINT UQ_Symptoms_Name UNIQUE (Symptom_Name)
);
GO

CREATE TABLE dbo.Doctors (
    Doctor_ID INT IDENTITY(1,1) NOT NULL,
    Clinic_ID INT NOT NULL,
    Full_Name NVARCHAR(120) NOT NULL,
    Years_Experience INT NOT NULL,
    Consultation_Fee DECIMAL(10,2) NOT NULL,
    Is_Available BIT NOT NULL CONSTRAINT DF_Doctors_IsAvailable DEFAULT 1,
    CONSTRAINT PK_Doctors PRIMARY KEY (Doctor_ID),
    CONSTRAINT FK_Doctors_Clinic FOREIGN KEY (Clinic_ID) REFERENCES dbo.Clinics(Clinic_ID),
    CONSTRAINT CK_Doctors_YearsExperience CHECK (Years_Experience >= 0),
    CONSTRAINT CK_Doctors_ConsultationFee CHECK (Consultation_Fee >= 0)
);
GO

/* ---------------------------
   Bridge entities (M:N)
---------------------------- */
CREATE TABLE dbo.Doctor_Specializations (
    Doctor_ID INT NOT NULL,
    Specialization_ID INT NOT NULL,
    CONSTRAINT PK_Doctor_Specializations PRIMARY KEY (Doctor_ID, Specialization_ID),
    CONSTRAINT FK_DoctorSpecializations_Doctor FOREIGN KEY (Doctor_ID) REFERENCES dbo.Doctors(Doctor_ID),
    CONSTRAINT FK_DoctorSpecializations_Specialization FOREIGN KEY (Specialization_ID) REFERENCES dbo.Specializations(Specialization_ID)
);
GO

CREATE TABLE dbo.Symptom_Specialization (
    Symptom_ID INT NOT NULL,
    Specialization_ID INT NOT NULL,
    Match_Weight DECIMAL(5,2) NOT NULL CONSTRAINT DF_SymptomSpecialization_Weight DEFAULT 1.00,
    CONSTRAINT PK_Symptom_Specialization PRIMARY KEY (Symptom_ID, Specialization_ID),
    CONSTRAINT FK_SymptomSpecialization_Symptom FOREIGN KEY (Symptom_ID) REFERENCES dbo.Symptoms(Symptom_ID),
    CONSTRAINT FK_SymptomSpecialization_Specialization FOREIGN KEY (Specialization_ID) REFERENCES dbo.Specializations(Specialization_ID),
    CONSTRAINT CK_SymptomSpecialization_Weight CHECK (Match_Weight > 0)
);
GO

/* ---------------------------
   Transaction entities
---------------------------- */
CREATE TABLE dbo.Patient_Symptoms (
    Patient_Symptom_ID BIGINT IDENTITY(1,1) NOT NULL,
    Patient_ID INT NOT NULL,
    Symptom_ID INT NOT NULL,
    Severity TINYINT NOT NULL,
    Recorded_At DATETIME2(0) NOT NULL CONSTRAINT DF_PatientSymptoms_RecordedAt DEFAULT SYSDATETIME(),
    CONSTRAINT PK_Patient_Symptoms PRIMARY KEY (Patient_Symptom_ID),
    CONSTRAINT FK_PatientSymptoms_Patient FOREIGN KEY (Patient_ID) REFERENCES dbo.Patients(Patient_ID),
    CONSTRAINT FK_PatientSymptoms_Symptom FOREIGN KEY (Symptom_ID) REFERENCES dbo.Symptoms(Symptom_ID),
    CONSTRAINT CK_PatientSymptoms_Severity CHECK (Severity BETWEEN 1 AND 5)
);
GO

CREATE TABLE dbo.Appointments (
    Appointment_ID INT IDENTITY(1,1) NOT NULL,
    Patient_ID INT NOT NULL,
    Doctor_ID INT NOT NULL,
    Appointment_Date DATETIME2(0) NOT NULL,
    Diagnosis NVARCHAR(300) NULL,
    Appointment_Status VARCHAR(30) NOT NULL,
    Created_At DATETIME2(0) NOT NULL CONSTRAINT DF_Appointments_CreatedAt DEFAULT SYSDATETIME(),
    CONSTRAINT PK_Appointments PRIMARY KEY (Appointment_ID),
    CONSTRAINT FK_Appointments_Patient FOREIGN KEY (Patient_ID) REFERENCES dbo.Patients(Patient_ID),
    CONSTRAINT FK_Appointments_Doctor FOREIGN KEY (Doctor_ID) REFERENCES dbo.Doctors(Doctor_ID),
    CONSTRAINT CK_Appointments_Status CHECK (Appointment_Status IN ('BOOKED', 'COMPLETED', 'CANCELLED'))
);
GO

CREATE TABLE dbo.Reviews (
    Review_ID INT IDENTITY(1,1) NOT NULL,
    Patient_ID INT NOT NULL,
    Doctor_ID INT NOT NULL,
    Rating TINYINT NOT NULL,
    Comment NVARCHAR(500) NULL,
    Review_Date DATETIME2(0) NOT NULL CONSTRAINT DF_Reviews_ReviewDate DEFAULT SYSDATETIME(),
    CONSTRAINT PK_Reviews PRIMARY KEY (Review_ID),
    CONSTRAINT FK_Reviews_Patient FOREIGN KEY (Patient_ID) REFERENCES dbo.Patients(Patient_ID),
    CONSTRAINT FK_Reviews_Doctor FOREIGN KEY (Doctor_ID) REFERENCES dbo.Doctors(Doctor_ID),
    CONSTRAINT CK_Reviews_Rating CHECK (Rating BETWEEN 1 AND 5)
);
GO

/* ---------------------------
   Performance indexes
---------------------------- */
CREATE INDEX IX_Doctors_Clinic ON dbo.Doctors(Clinic_ID);
CREATE INDEX IX_DoctorSpecializations_Specialization ON dbo.Doctor_Specializations(Specialization_ID, Doctor_ID);
CREATE INDEX IX_SymptomSpecialization_Specialization ON dbo.Symptom_Specialization(Specialization_ID, Symptom_ID);
CREATE INDEX IX_PatientSymptoms_Patient_Recorded ON dbo.Patient_Symptoms(Patient_ID, Recorded_At DESC);
CREATE INDEX IX_Reviews_Doctor_Rating ON dbo.Reviews(Doctor_ID, Rating);
CREATE INDEX IX_Appointments_Doctor_Date_Status ON dbo.Appointments(Doctor_ID, Appointment_Date, Appointment_Status);
GO
