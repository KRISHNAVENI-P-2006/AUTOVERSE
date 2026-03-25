# Autoverse by Safari Motors

A full-stack Car Dealership Management System built with Flask (Python) and SQLite.

---

## Table of Contents
- Project Overview
- Tech Stack
- Features
- Database Schema
- Project Structure
- Installation & Setup
- Login Credentials
- User Roles
- URL Reference
- Running the App

---

## Project Overview
Autoverse is a web-based dealership management system that serves three types of users — Admin, Staff, and Customer — each with a completely separate interface, color theme, and feature set.

All three portals are accessed through a single login page, which automatically routes users to the correct dashboard based on their role.

---

## Tech Stack

Backend: Python 3, Flask  
Database: SQLite (via sqlite3)  
ORM: Raw SQL with sqlite3.Row  
Frontend: HTML, CSS, JavaScript  
Authentication: Werkzeug password hashing, Flask sessions  
Charts: Chart.js (CDN)  
Fonts: Google Fonts (Fraunces, Plus Jakarta Sans, Syne, Poppins)

---

## Features

### Admin Portal
- Full CRUD for vehicles, manufacturers, customers, staff, and sales  
- Revenue reports with charts by month, showroom, manufacturer, and fuel type  
- Staff performance tracking with sales count and total revenue  
- Inquiry management with chat interface  
- Test drive booking overview across all showrooms  
- User account management including creation, role assignment, and deletion  

---

### Staff Portal
- Branch-restricted access to showroom data  
- Chat-based inquiry management with unread notification badge  
- Test drive booking management including confirm, complete, and cancel  
- Record new sales with automatic vehicle status update  
- Add and edit vehicles in inventory  
- Read-only access to customer list  

---

### Customer Portal
- Browse cars in a card grid with images, colour options, and EMI calculator  
- Vehicle detail page with specifications and EMI plans  
- Wishlist to save favourite vehicles  
- Send inquiries and chat with staff  
- Book test drives with live slot availability  
- View purchase history  
- Update profile and change password  

---

### System-wide Features
- Role-based authentication using decorators  
- Live notification badges with periodic polling  
- Branch-based data isolation enforced at SQL level  
- Password hashing using Werkzeug  
- Session management with Flask  
- Forgot password with two-step username verification  
- Fully responsive layout  

---

## Database Schema

The application uses 10 tables with relational mappings:

- Users — login credentials and roles  
- Manufacturer — car brands  
- Vehicle — inventory linked to manufacturer  
- Customer — customer profiles  
- Sales_Staff — staff profiles  
- Sales — completed transactions  
- Inquiry — chat threads  
- InquiryMessage — messages within inquiries  
- Wishlist — saved vehicles  
- TestDrive — booking slots  

---

### Key Relationships
- Users to Customer and Sales_Staff (one-to-one via user_id)  
- Manufacturer to Vehicle (one-to-many)  
- Vehicle to Sales, Inquiry, Wishlist, and TestDrive (one-to-many)  
- Inquiry to InquiryMessage (one-to-many, supports chat system)  
- Branch stored as TEXT in Inquiry and TestDrive for access control  

---
