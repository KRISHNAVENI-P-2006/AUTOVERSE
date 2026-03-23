import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'dealership.db')

BRANCHES = [
    'Kochi Showroom',
    'Bangalore Showroom',
    'Chennai Showroom',
    'Mumbai Showroom',
    'Delhi Showroom',
]

# Real car image URLs mapped by model name
CAR_IMAGES = {
    'Swift':        'https://imgd.aeplcdn.com/664x374/n/cw/ec/159297/swift-exterior-right-front-three-quarter-2.jpeg?isig=0&q=80',
    'Baleno':       'https://imgd.aeplcdn.com/664x374/n/cw/ec/130585/baleno-exterior-right-front-three-quarter-77.jpeg?isig=0&q=80',
    'Brezza':       'https://imgd.aeplcdn.com/664x374/n/cw/ec/134297/brezza-exterior-right-front-three-quarter-3.jpeg?isig=0&q=80',
    'Creta':        'https://imgd.aeplcdn.com/664x374/n/cw/ec/106815/creta-exterior-right-front-three-quarter-2.jpeg?isig=0&q=80',
    'i20':          'https://imgd.aeplcdn.com/664x374/n/cw/ec/40087/i20-exterior-right-front-three-quarter-163068.jpeg?isig=0&q=80',
    'Alcazar':      'https://imgd.aeplcdn.com/664x374/n/cw/ec/115777/alcazar-exterior-right-front-three-quarter-2.jpeg?isig=0&q=80',
    'Nexon':        'https://imgd.aeplcdn.com/664x374/n/cw/ec/141891/nexon-exterior-right-front-three-quarter-2.jpeg?isig=0&q=80',
    'Harrier':      'https://imgd.aeplcdn.com/664x374/n/cw/ec/39345/harrier-exterior-right-front-three-quarter-22.jpeg?isig=0&q=80',
    'Scorpio-N':    'https://imgd.aeplcdn.com/664x374/n/cw/ec/130583/scorpio-n-exterior-right-front-three-quarter-2.jpeg?isig=0&q=80',
    'XUV700':       'https://imgd.aeplcdn.com/664x374/n/cw/ec/42355/xuv700-exterior-right-front-three-quarter-3.jpeg?isig=0&q=80',
    'City':         'https://imgd.aeplcdn.com/664x374/n/cw/ec/134297/city-exterior-right-front-three-quarter-4.jpeg?isig=0&q=80',
    'Innova Crysta':'https://imgd.aeplcdn.com/664x374/n/cw/ec/51435/innova-crysta-exterior-right-front-three-quarter-2.jpeg?isig=0&q=80',
    'Seltos':       'https://imgd.aeplcdn.com/664x374/n/cw/ec/130591/seltos-exterior-right-front-three-quarter-4.jpeg?isig=0&q=80',
    'Hector':       'https://imgd.aeplcdn.com/664x374/n/cw/ec/88155/hector-exterior-right-front-three-quarter-3.jpeg?isig=0&q=80',
}

FALLBACK_IMAGE = 'https://imgd.aeplcdn.com/664x374/n/cw/ec/106815/creta-exterior-right-front-three-quarter-2.jpeg?isig=0&q=80'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript('''
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','staff','customer'))
        );

        CREATE TABLE IF NOT EXISTS Manufacturer (
            manufacturer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country TEXT,
            founded_year INTEGER,
            website TEXT
        );

        CREATE TABLE IF NOT EXISTS Vehicle (
            vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
            manufacturer_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            year INTEGER NOT NULL,
            price REAL NOT NULL,
            color TEXT,
            available_colors TEXT,
            fuel_type TEXT,
            transmission TEXT,
            mileage INTEGER DEFAULT 0,
            description TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'available' CHECK(status IN ('available','sold','reserved')),
            FOREIGN KEY (manufacturer_id) REFERENCES Manufacturer(manufacturer_id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS Customer (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS Sales_Staff (
            staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            branch TEXT,
            salary REAL,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS Sales (
            sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL,
            sale_price REAL NOT NULL,
            sale_date TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES Vehicle(vehicle_id) ON DELETE RESTRICT,
            FOREIGN KEY (customer_id) REFERENCES Customer(customer_id) ON DELETE RESTRICT,
            FOREIGN KEY (staff_id) REFERENCES Sales_Staff(staff_id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS Inquiry (
            inquiry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            branch TEXT NOT NULL,
            staff_id INTEGER,
            inquiry_date TEXT NOT NULL,
            status TEXT DEFAULT 'open' CHECK(status IN ('open','closed')),
            FOREIGN KEY (customer_id) REFERENCES Customer(customer_id) ON DELETE CASCADE,
            FOREIGN KEY (vehicle_id) REFERENCES Vehicle(vehicle_id) ON DELETE CASCADE,
            FOREIGN KEY (staff_id) REFERENCES Sales_Staff(staff_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS InquiryMessage (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            inquiry_id INTEGER NOT NULL,
            sender_role TEXT NOT NULL CHECK(sender_role IN ('customer','staff','admin')),
            sender_name TEXT NOT NULL,
            message TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (inquiry_id) REFERENCES Inquiry(inquiry_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS Wishlist (
            wishlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            added_date TEXT NOT NULL,
            UNIQUE(customer_id, vehicle_id),
            FOREIGN KEY (customer_id) REFERENCES Customer(customer_id) ON DELETE CASCADE,
            FOREIGN KEY (vehicle_id) REFERENCES Vehicle(vehicle_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS TestDrive (
            booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            branch TEXT NOT NULL,
            preferred_date TEXT NOT NULL,
            preferred_time TEXT NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending','confirmed','completed','cancelled')),
            notes TEXT,
            booked_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES Customer(customer_id) ON DELETE CASCADE,
            FOREIGN KEY (vehicle_id) REFERENCES Vehicle(vehicle_id) ON DELETE CASCADE
        );
    ''')

    # Seed admin
    if not c.execute("SELECT 1 FROM Users WHERE username='admin'").fetchone():
        c.execute("INSERT INTO Users (username,password,role) VALUES (?,?,?)",
                  ('admin', generate_password_hash('admin123'), 'admin'))

    # Seed manufacturers
    if c.execute("SELECT COUNT(*) FROM Manufacturer").fetchone()[0] == 0:
        c.executemany("INSERT INTO Manufacturer (name,country,founded_year,website) VALUES (?,?,?,?)", [
            ('Maruti Suzuki', 'India/Japan', 1981, 'https://marutisuzuki.com'),
            ('Hyundai',       'South Korea', 1967, 'https://hyundai.com'),
            ('Tata Motors',   'India',       1945, 'https://tatamotors.com'),
            ('Mahindra',      'India',       1945, 'https://mahindra.com'),
            ('Honda',         'Japan',       1948, 'https://honda.com'),
            ('Toyota',        'Japan',       1937, 'https://toyota.com'),
            ('Kia',           'South Korea', 1944, 'https://kia.com'),
            ('MG Motor',      'UK/China',    1924, 'https://mgmotor.co.in'),
        ])

    if c.execute("SELECT COUNT(*) FROM Vehicle").fetchone()[0] == 0:
        vehicles = [
            (1,'Swift',2024,649000,'Pearl White','Pearl White,Magma Grey,Sizzling Red,Midnight Black,Lucent Orange','Petrol','Manual',0,"India's most loved hatchback. Sporty design with best-in-class fuel efficiency of 23.76 km/l.",CAR_IMAGES['Swift'],'available'),
            (1,'Baleno',2024,699000,'Grandeur Grey','Grandeur Grey,Pearl Arctic White,Splendid Silver,Midnight Black Blue,Rebel Red','Petrol','Automatic',0,'Premium hatchback with futuristic design. Features Heads-Up Display and 360 camera.',CAR_IMAGES['Baleno'],'available'),
            (1,'Brezza',2024,849000,'Sizzling Red','Sizzling Red,Pearl Arctic White,Splendid Silver,Midnight Black Blue,Brave Khaki','Petrol','Automatic',0,'Bold compact SUV with a 1.5L engine, panoramic sunroof and 9-inch SmartPlay Pro+ system.',CAR_IMAGES['Brezza'],'available'),
            (2,'Creta',2024,1099000,'Atlas White','Atlas White,Abyss Black,Typhoon Silver,Ranger Khaki,Fiery Red','Petrol','Automatic',0,"India's No.1 SUV. Segment-first panoramic sunroof, ADAS Level 2, and Bose 8-speaker system.",CAR_IMAGES['Creta'],'available'),
            (2,'i20',2024,749000,'Fiery Red','Fiery Red,Atlas White,Polar White,Typhoon Silver,Midnight Black','Petrol','Manual',4500,'Sporty premium hatchback with 10.25 inch touchscreen and sunroof.',CAR_IMAGES['i20'],'available'),
            (2,'Alcazar',2024,1699000,'Abyss Black','Abyss Black,Atlas White,Typhoon Silver,Fiery Red','Diesel','Automatic',0,'Luxurious 6/7-seater SUV with Dual Screen Dashboard and BOSE premium sound.',CAR_IMAGES['Alcazar'],'available'),
            (3,'Nexon',2024,849000,'Calgary White','Calgary White,Flame Red,Daytona Grey,Tropical Mist,Creative Ocean','Petrol','Automatic',0,"India's safest car. 5-star Global NCAP rating. Now with ADAS and ventilated seats.",CAR_IMAGES['Nexon'],'available'),
            (3,'Harrier',2024,1499000,'Daytona Grey','Daytona Grey,Calgary White,Orcus White,Oberon Black,Calypso Red','Diesel','Automatic',0,'Premium SUV built on Land Rover-derived OMEGA architecture with panoramic sunroof.',CAR_IMAGES['Harrier'],'available'),
            (4,'Scorpio-N',2024,1349000,'Napoli Black','Napoli Black,Everest White,Deep Forest,Red Rage,Burnt Sienna','Diesel','Manual',0,'Born of an adventure. 4WD, ADAS, Sony 3D sound — King of SUVs.',CAR_IMAGES['Scorpio-N'],'available'),
            (4,'XUV700',2024,1399000,'Everest White','Everest White,Napoli Black,Deep Forest,Red Rage,Burnt Sienna','Petrol','Automatic',0,'Game-changing SUV with Advanced Driver Assistance System and panoramic sunroof.',CAR_IMAGES['XUV700'],'available'),
            (5,'City',2024,1199000,'Platinum White Pearl','Platinum White Pearl,Meteoroid Gray,Lunar Silver,Golden Brown','Petrol','CVT',0,'Premium sedan with Honda Sensing ADAS suite and 17.78cm touchscreen.',CAR_IMAGES['City'],'available'),
            (6,'Innova Crysta',2024,1999000,'Super White','Super White,Silver Metallic,Bronze Mica Metallic,Attitude Black Mica','Diesel','Automatic',0,"India's most trusted MPV. Ultimate comfort for long journeys with captain seats.",CAR_IMAGES['Innova Crysta'],'available'),
            (7,'Seltos',2024,1099000,'Gravity Grey','Gravity Grey,Clear White,Intense Red,Pewter Olive,Aurora Black Pearl','Petrol','Automatic',0,'Feature-rich SUV with BOSE premium 8-speaker sound and panoramic sunroof.',CAR_IMAGES['Seltos'],'available'),
            (8,'Hector',2024,1499000,'Starry Night Blue','Starry Night Blue,Candy White,Glaze Red,Dual Tone Black Roof','Petrol','CVT',0,"India's first internet car with i-SMART Next Gen and 35.56cm touchscreen.",CAR_IMAGES['Hector'],'available'),
        ]
        c.executemany("""INSERT INTO Vehicle
            (manufacturer_id,model,year,price,color,available_colors,fuel_type,
             transmission,mileage,description,image_url,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", vehicles)

    staff_seeds = [
        ('Arjun Nair',    '9876543210','arjun@autoverse.in',  'Kochi Showroom',      65000,'arjun_nair',   'arjun123'),
        ('Priya Sharma',  '9876543211','priya@autoverse.in',  'Bangalore Showroom',  62000,'priya_sharma', 'priya123'),
        ('Rahul Verma',   '9876543212','rahul@autoverse.in',  'Chennai Showroom',    60000,'rahul_verma',  'rahul123'),
        ('Sneha Pillai',  '9876543213','sneha@autoverse.in',  'Mumbai Showroom',     63000,'sneha_pillai', 'sneha123'),
        ('Vikram Singh',  '9876543214','vikram@autoverse.in', 'Delhi Showroom',      67000,'vikram_singh', 'vikram123'),
    ]
    for name,phone,email,branch,salary,uname,pwd in staff_seeds:
        if not c.execute("SELECT 1 FROM Users WHERE username=?", (uname,)).fetchone():
            c.execute("INSERT INTO Users (username,password,role) VALUES (?,?,?)",
                      (uname, generate_password_hash(pwd), 'staff'))
            uid = c.lastrowid
            c.execute("INSERT INTO Sales_Staff (name,phone,email,branch,salary,user_id) VALUES (?,?,?,?,?,?)",
                      (name,phone,email,branch,salary,uid))

    cust_seeds = [
        ('Kavya Menon','9845012345','kavya@gmail.com','Flat 4B, Marine Drive, Kochi - 682001','kavya_menon','kavya123'),
        ('Rohan Iyer', '9845012346','rohan@gmail.com','12, Koramangala, Bangalore - 560034',  'rohan_iyer', 'rohan123'),
    ]
    for name,phone,email,address,uname,pwd in cust_seeds:
        if not c.execute("SELECT 1 FROM Users WHERE username=?", (uname,)).fetchone():
            c.execute("INSERT INTO Users (username,password,role) VALUES (?,?,?)",
                      (uname, generate_password_hash(pwd), 'customer'))
            uid = c.lastrowid
            c.execute("INSERT INTO Customer (name,phone,email,address,user_id) VALUES (?,?,?,?,?)",
                      (name,phone,email,address,uid))

    conn.commit()
    conn.close()
    print("Database initialised.")
