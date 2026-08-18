CREATE DATABASE IF NOT EXISTS cruise_booking;

USE cruise_booking;

-- Users: Admin, Agent, Customer
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('ADMIN', 'AGENT', 'CUSTOMER') NOT NULL,
    status ENUM('ACTIVE', 'INACTIVE') DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cruise ships
CREATE TABLE cruises (
    cruise_id INT AUTO_INCREMENT PRIMARY KEY,
    cruise_line VARCHAR(100) NOT NULL,
    ship VARCHAR(100) NOT NULL,
    destination VARCHAR(100) NOT NULL,
    status ENUM('ACTIVE', 'INACTIVE') DEFAULT 'ACTIVE'
);

-- Specific cruise departure
CREATE TABLE cruise_departures (
    departure_id INT AUTO_INCREMENT PRIMARY KEY,
    cruise_id INT NOT NULL,
    departure_date DATE NOT NULL,
    return_date DATE NOT NULL,
    nights INT NOT NULL,
    adult_fare DECIMAL(10,2) NOT NULL,
    capacity INT NOT NULL,
    status ENUM('OPEN', 'CLOSED', 'CANCELLED') DEFAULT 'OPEN',

    FOREIGN KEY (cruise_id)
        REFERENCES cruises(cruise_id)
);

-- Optional services
CREATE TABLE optional_services (
    service_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    pricing_type ENUM(
        'PER_PASSENGER',
        'PER_PASSENGER_NIGHT'
    ) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    status ENUM('ACTIVE', 'INACTIVE') DEFAULT 'ACTIVE'
);

-- Promotional codes
CREATE TABLE promotional_codes (
    promotion_id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,

    discount_type ENUM(
        'PERCENTAGE',
        'FIXED'
    ) NOT NULL,

    discount_value DECIMAL(10,2) NOT NULL,

    valid_from DATE NOT NULL,
    valid_until DATE NOT NULL,

    max_uses_per_customer INT NOT NULL,

    status ENUM('ACTIVE', 'INACTIVE') DEFAULT 'ACTIVE'
);

-- Orders
CREATE TABLE orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    order_reference VARCHAR(30) UNIQUE NOT NULL,

    customer_id INT NOT NULL,
    departure_id INT NOT NULL,

    adult_count INT NOT NULL,
    child_count INT NOT NULL,
    total_passengers INT NOT NULL,

    base_fare DECIMAL(10,2) NOT NULL,
    group_discount DECIMAL(10,2) DEFAULT 0,
    promotion_discount DECIMAL(10,2) DEFAULT 0,
    services_total DECIMAL(10,2) DEFAULT 0,
    tax_amount DECIMAL(10,2) DEFAULT 0,
    final_amount DECIMAL(10,2) NOT NULL,

    promotion_id INT,

    status ENUM(
        'PENDING',
        'CONFIRMED',
        'CANCELLED'
    ) DEFAULT 'PENDING',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (customer_id)
        REFERENCES users(user_id),

    FOREIGN KEY (departure_id)
        REFERENCES cruise_departures(departure_id),

    FOREIGN KEY (promotion_id)
        REFERENCES promotional_codes(promotion_id)
);

-- Passengers
CREATE TABLE passengers (
    passenger_id INT AUTO_INCREMENT PRIMARY KEY,

    order_id INT NOT NULL,

    name VARCHAR(100) NOT NULL,
    date_of_birth DATE NOT NULL,

    age_at_booking INT NOT NULL,

    passenger_type ENUM(
        'ADULT',
        'CHILD'
    ) NOT NULL,

    fare_percentage DECIMAL(5,2) NOT NULL,
    fare_amount DECIMAL(10,2) NOT NULL,

    FOREIGN KEY (order_id)
        REFERENCES orders(order_id)
);

-- Services selected in an order
CREATE TABLE order_services (
    order_service_id INT AUTO_INCREMENT PRIMARY KEY,

    order_id INT NOT NULL,
    service_id INT NOT NULL,

    quantity INT NOT NULL,

    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL,

    FOREIGN KEY (order_id)
        REFERENCES orders(order_id),

    FOREIGN KEY (service_id)
        REFERENCES optional_services(service_id)
);

-- Promotion usage
CREATE TABLE promotion_redemptions (
    redemption_id INT AUTO_INCREMENT PRIMARY KEY,

    promotion_id INT NOT NULL,
    customer_id INT NOT NULL,
    order_id INT NOT NULL,

    discount_amount DECIMAL(10,2) NOT NULL,

    redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (promotion_id)
        REFERENCES promotional_codes(promotion_id),

    FOREIGN KEY (customer_id)
        REFERENCES users(user_id),

    FOREIGN KEY (order_id)
        REFERENCES orders(order_id)
);

-- Historical pricing snapshot
CREATE TABLE order_pricing (
    pricing_id INT AUTO_INCREMENT PRIMARY KEY,

    order_id INT UNIQUE NOT NULL,

    adult_fare DECIMAL(10,2) NOT NULL,
    nights INT NOT NULL,

    group_discount_rate DECIMAL(5,2) NOT NULL,
    group_discount_amount DECIMAL(10,2) NOT NULL,

    promotion_code VARCHAR(50),
    promotion_type VARCHAR(20),
    promotion_value DECIMAL(10,2),
    promotion_discount_amount DECIMAL(10,2),

    services_total DECIMAL(10,2) NOT NULL,

    tax_rate DECIMAL(5,2) NOT NULL,
    tax_amount DECIMAL(10,2) NOT NULL,

    subtotal DECIMAL(10,2) NOT NULL,
    final_amount DECIMAL(10,2) NOT NULL,

    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (order_id)
        REFERENCES orders(order_id)
);