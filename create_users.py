from auth import create_user


create_user(
    "System Admin",
    "admin@gmail.com",
    "admin123",
    "ADMIN"
)

create_user(
    "Cruise Agent",
    "agent@gmail.com",
    "agent123",
    "AGENT"
)

print("Admin and Agent created successfully!")