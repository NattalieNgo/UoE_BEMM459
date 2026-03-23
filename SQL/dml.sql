/*
Doctor Recommendation System - SQL Server DML
Sample seed data for demo/testing recommendation flow
*/

SET XACT_ABORT ON;
GO

/* ---------------------------
   Clinics
---------------------------- */
INSERT INTO dbo.Clinics (Clinic_Name, City, Address_Line)
VALUES
(N'CityCare Clinic', N'Exeter', N'12 Queen Street'),
(N'Riverside Medical Centre', N'Exeter', N'88 River Road'),
(N'North Health Hub', N'Plymouth', N'5 North Avenue');
GO

/* ---------------------------
   Specializations
---------------------------- */
INSERT INTO dbo.Specializations (Specialization_Name)
VALUES
(N'Cardiology'),
(N'Dermatology'),
(N'Neurology'),
(N'General Practice'),
(N'Pulmonology'),
(N'Orthopedics');
GO

/* ---------------------------
   Symptoms
---------------------------- */
INSERT INTO dbo.Symptoms (Symptom_Name)
VALUES
(N'Chest Pain'),
(N'Shortness of Breath'),
(N'Skin Rash'),
(N'Itchy Skin'),
(N'Headache'),
(N'Dizziness'),
(N'Fever'),
(N'Cough'),
(N'Back Pain'),
(N'Joint Pain');
GO

/* ---------------------------
   Symptom -> Specialization mapping
---------------------------- */
INSERT INTO dbo.Symptom_Specialization (Symptom_ID, Specialization_ID, Match_Weight)
VALUES
(1, 1, 1.90),  -- Chest Pain -> Cardiology
(2, 1, 1.60),  -- Shortness of Breath -> Cardiology
(2, 5, 1.50),  -- Shortness of Breath -> Pulmonology
(3, 2, 1.70),  -- Skin Rash -> Dermatology
(4, 2, 1.60),  -- Itchy Skin -> Dermatology
(5, 3, 1.70),  -- Headache -> Neurology
(6, 3, 1.60),  -- Dizziness -> Neurology
(7, 4, 1.10),  -- Fever -> General Practice
(8, 5, 1.80),  -- Cough -> Pulmonology
(9, 6, 1.70),  -- Back Pain -> Orthopedics
(10, 6, 1.80); -- Joint Pain -> Orthopedics
GO

/* ---------------------------
   Doctors
---------------------------- */
INSERT INTO dbo.Doctors (Clinic_ID, Full_Name, Years_Experience, Consultation_Fee, Is_Available)
VALUES
(1, N'Dr. Alice Carter', 12, 95.00, 1),
(1, N'Dr. Brian Lee', 8, 80.00, 1),
(2, N'Dr. Chloe Nguyen', 15, 120.00, 1),
(2, N'Dr. Daniel Smith', 6, 70.00, 1),
(3, N'Dr. Emma Patel', 10, 90.00, 1),
(3, N'Dr. Frank Wilson', 9, 85.00, 1);
GO

/* ---------------------------
   Doctor -> Specialization mapping
---------------------------- */
INSERT INTO dbo.Doctor_Specializations (Doctor_ID, Specialization_ID)
VALUES
(1, 1), -- Alice -> Cardiology
(1, 4), -- Alice -> GP
(2, 2), -- Brian -> Dermatology
(2, 4), -- Brian -> GP
(3, 3), -- Chloe -> Neurology
(4, 5), -- Daniel -> Pulmonology
(4, 4), -- Daniel -> GP
(5, 6), -- Emma -> Orthopedics
(5, 4), -- Emma -> GP
(6, 1); -- Frank -> Cardiology
GO

/* ---------------------------
   Patients
---------------------------- */
INSERT INTO dbo.Patients (Full_Name, Gender, Date_Of_Birth, Phone, Email)
VALUES
(N'John Smith', 'M', '1998-05-20', '07111111111', 'john.smith@email.com'),
(N'Maria Garcia', 'F', '1995-11-03', '07222222222', 'maria.garcia@email.com'),
(N'Ahmed Hassan', 'M', '1991-04-18', '07333333333', 'ahmed.hassan@email.com'),
(N'Sophia Brown', 'F', '2000-09-09', '07444444444', 'sophia.brown@email.com');
GO

/* ---------------------------
   Patient symptoms (recent and historical)
---------------------------- */
INSERT INTO dbo.Patient_Symptoms (Patient_ID, Symptom_ID, Severity, Recorded_At)
VALUES
-- Patient 1: Chest + breathing concern
(1, 1, 4, DATEADD(DAY, -2, SYSDATETIME())),
(1, 2, 3, DATEADD(DAY, -2, SYSDATETIME())),
(1, 5, 2, DATEADD(DAY, -20, SYSDATETIME())),

-- Patient 2: Skin concern
(2, 3, 4, DATEADD(DAY, -1, SYSDATETIME())),
(2, 4, 5, DATEADD(DAY, -1, SYSDATETIME())),

-- Patient 3: Neurology concern
(3, 5, 4, DATEADD(DAY, -3, SYSDATETIME())),
(3, 6, 3, DATEADD(DAY, -3, SYSDATETIME())),

-- Patient 4: Ortho concern
(4, 9, 4, DATEADD(DAY, -1, SYSDATETIME())),
(4, 10, 5, DATEADD(DAY, -1, SYSDATETIME()));
GO

/* ---------------------------
   Appointments
---------------------------- */
INSERT INTO dbo.Appointments (Patient_ID, Doctor_ID, Appointment_Date, Diagnosis, Appointment_Status)
VALUES
(1, 1, DATEADD(DAY, -10, SYSDATETIME()), N'Possible angina, follow-up required', 'COMPLETED'),
(1, 6, DATEADD(DAY, 2, SYSDATETIME()), NULL, 'BOOKED'),
(2, 2, DATEADD(DAY, -7, SYSDATETIME()), N'Contact dermatitis', 'COMPLETED'),
(2, 2, DATEADD(DAY, 5, SYSDATETIME()), NULL, 'BOOKED'),
(3, 3, DATEADD(DAY, -5, SYSDATETIME()), N'Migraine', 'COMPLETED'),
(4, 5, DATEADD(DAY, -4, SYSDATETIME()), N'Muscle strain', 'COMPLETED'),
(4, 5, DATEADD(DAY, 1, SYSDATETIME()), NULL, 'BOOKED'),
(3, 4, DATEADD(DAY, 3, SYSDATETIME()), NULL, 'BOOKED');
GO

/* ---------------------------
   Reviews
---------------------------- */
INSERT INTO dbo.Reviews (Patient_ID, Doctor_ID, Rating, Comment, Review_Date)
VALUES
(1, 1, 5, N'Very clear explanation and care.', DATEADD(DAY, -9, SYSDATETIME())),
(1, 6, 4, N'Good but waiting time was a bit long.', DATEADD(DAY, -30, SYSDATETIME())),
(2, 2, 5, N'Treatment worked quickly.', DATEADD(DAY, -6, SYSDATETIME())),
(3, 3, 4, N'Helpful advice on migraine management.', DATEADD(DAY, -4, SYSDATETIME())),
(3, 4, 4, N'Good overall consultation.', DATEADD(DAY, -40, SYSDATETIME())),
(4, 5, 5, N'Excellent diagnosis and follow-up plan.', DATEADD(DAY, -3, SYSDATETIME())),
(2, 4, 3, N'Average consultation.', DATEADD(DAY, -18, SYSDATETIME()));
GO
