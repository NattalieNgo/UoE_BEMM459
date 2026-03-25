-- Simple DDL for Doctor Recommendation System

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

CREATE TABLE dbo.Patients (
    Patient_ID INT IDENTITY(1,1) PRIMARY KEY,
    Full_Name NVARCHAR(120) NOT NULL,
    Gender CHAR(1),
    Date_Of_Birth DATE,
    Phone VARCHAR(20),
    Email VARCHAR(120)
);

CREATE TABLE dbo.Clinics (
    Clinic_ID INT IDENTITY(1,1) PRIMARY KEY,
    Clinic_Name NVARCHAR(150) NOT NULL,
    City NVARCHAR(80),
    Address_Line NVARCHAR(255)
);

CREATE TABLE dbo.Specializations (
    Specialization_ID INT IDENTITY(1,1) PRIMARY KEY,
    Specialization_Name NVARCHAR(120) NOT NULL
);

CREATE TABLE dbo.Symptoms (
    Symptom_ID INT IDENTITY(1,1) PRIMARY KEY,
    Symptom_Name NVARCHAR(120) NOT NULL
);

CREATE TABLE dbo.Doctors (
    Doctor_ID INT IDENTITY(1,1) PRIMARY KEY,
    Clinic_ID INT NOT NULL,
    Full_Name NVARCHAR(120) NOT NULL,
    Years_Experience INT NOT NULL,
    Consultation_Fee DECIMAL(10,2) NOT NULL,
    Is_Available BIT NOT NULL DEFAULT 1,
    FOREIGN KEY (Clinic_ID) REFERENCES dbo.Clinics(Clinic_ID)
);

CREATE TABLE dbo.Doctor_Specializations (
    Doctor_ID INT NOT NULL,
    Specialization_ID INT NOT NULL,
    PRIMARY KEY (Doctor_ID, Specialization_ID),
    FOREIGN KEY (Doctor_ID) REFERENCES dbo.Doctors(Doctor_ID),
    FOREIGN KEY (Specialization_ID) REFERENCES dbo.Specializations(Specialization_ID)
);

CREATE TABLE dbo.Symptom_Specialization (
    Symptom_ID INT NOT NULL,
    Specialization_ID INT NOT NULL,
    Match_Weight DECIMAL(5,2) NOT NULL DEFAULT 1.00,
    PRIMARY KEY (Symptom_ID, Specialization_ID),
    FOREIGN KEY (Symptom_ID) REFERENCES dbo.Symptoms(Symptom_ID),
    FOREIGN KEY (Specialization_ID) REFERENCES dbo.Specializations(Specialization_ID)
);

CREATE TABLE dbo.Patient_Symptoms (
    Patient_Symptom_ID BIGINT IDENTITY(1,1) PRIMARY KEY,
    Patient_ID INT NOT NULL,
    Symptom_ID INT NOT NULL,
    Severity TINYINT NOT NULL,
    Recorded_At DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    FOREIGN KEY (Patient_ID) REFERENCES dbo.Patients(Patient_ID),
    FOREIGN KEY (Symptom_ID) REFERENCES dbo.Symptoms(Symptom_ID)
);

CREATE TABLE dbo.Appointments (
    Appointment_ID INT IDENTITY(1,1) PRIMARY KEY,
    Patient_ID INT NOT NULL,
    Doctor_ID INT NOT NULL,
    Appointment_Date DATETIME2(0) NOT NULL,
    Diagnosis NVARCHAR(300),
    Appointment_Status VARCHAR(30) NOT NULL,
    Created_At DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    FOREIGN KEY (Patient_ID) REFERENCES dbo.Patients(Patient_ID),
    FOREIGN KEY (Doctor_ID) REFERENCES dbo.Doctors(Doctor_ID)
);

CREATE TABLE dbo.Reviews (
    Review_ID INT IDENTITY(1,1) PRIMARY KEY,
    Patient_ID INT NOT NULL,
    Doctor_ID INT NOT NULL,
    Rating TINYINT NOT NULL,
    Comment NVARCHAR(500),
    Review_Date DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    FOREIGN KEY (Patient_ID) REFERENCES dbo.Patients(Patient_ID),
    FOREIGN KEY (Doctor_ID) REFERENCES dbo.Doctors(Doctor_ID)
);
