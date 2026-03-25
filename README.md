**Autoverse by Safari Motors**
A full-stack Car Dealership Management System built with Flask (Python) and SQLite.

**Table of Contents**

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


__Project Overview__
Autoverse is a web-based dealership management system that serves three types of users — Admin, Staff, and Customer — each with a completely separate interface, color theme, and set of features. All three portals are accessed through a single login page that automatically routes each user to the correct dashboard based on their role.

__Tech Stack__
LayerTechnologyBackendPython 3, FlaskDatabaseSQLite (via Python sqlite3)ORMRaw SQL with sqlite3.RowFrontendHTML, CSS, JavaScriptAuthWerkzeug password hashing, Flask sessionsChartsChart.js 4.4 (CDN)FontsGoogle Fonts (Fraunces, Plus Jakarta Sans, Syne, Poppins)

__Features__
##Admin Portal

- Full CRUD for vehicles, manufacturers, customers, staff, and sales
- Revenue reports with charts — by month, showroom, manufacturer, fuel type
- Staff performance table — sales count and total revenue per person
- Inquiry management across all branches with chat interface
- Test drive bookings overview across all showrooms
- User account management — create, assign roles, delete

##Staff Portal

- Branch-restricted access — only sees own showroom's data
- Chat-based inquiry management with real-time unread badge
- Test drive booking management — confirm, complete, cancel
- Record new sales with auto vehicle status update
- Add and edit vehicles in inventory
- Read-only customer list

## Customer Portal

Browse cars in a card grid with real images, colour swatches, and EMI calculator
Vehicle detail page with full specs, all available colours, and 6 EMI plan options
Wishlist to save favourite vehicles
Send inquiries to a specific showroom and chat with staff
Book test drives with live slot availability per branch
View purchase history
Update profile and change password

System-wide

Role-based authentication with @login_required and @role_required decorators
Live notification badges polling every 15 seconds — unread inquiries and pending test drives
Branch-based data isolation — enforced at SQL query level
Password hashing with Werkzeug bcrypt
Session management with Flask sessions
Forgot password with 2-step username verification
Fully responsive layout


Database Schema
The app uses 10 tables with full foreign key relationships.
Users           — login credentials and role for all users
Manufacturer    — car brands
Vehicle         — car inventory linked to manufacturer
Customer        — customer profiles linked to Users
Sales_Staff     — staff profiles linked to Users
Sales           — completed sales (vehicle + customer + staff)
Inquiry         — chat threads between customer and a branch
InquiryMessage  — individual messages inside an inquiry thread
Wishlist        — vehicles saved by a customer
TestDrive       — test drive slot bookings
Key relationships:

Users → Customer and Sales_Staff (one-to-one via user_id FK)
Manufacturer → Vehicle (one-to-many)
Vehicle → Sales, Inquiry, Wishlist, TestDrive (one-to-many)
Inquiry → InquiryMessage (one-to-many, powers the chat)
branch stored as TEXT in Inquiry and TestDrive — used to filter staff access at query level
