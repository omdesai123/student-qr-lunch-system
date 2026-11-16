"""
Script to generate a realistic CSV file containing 500 college students
for testing bulk import and system scalability.
"""

import csv
import random

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Reyansh", "Muhammad", "Sai", "Ayaan", "Krishna",
    "Ishaan", "Shaurya", "Atharva", "Dhruv", "Kabir", "Rohan", "Ananya", "Diya", "Saanvi", "Aadhya",
    "Kiara", "Pari", "Fatima", "Anushka", "Myra", "Isha", "Riya", "Kavya", "Sneha", "Tanvi",
    "Neha", "Pooja", "Vikram", "Rahul", "Karthik", "Siddharth", "Gautam", "Manish", "Deepak", "Nikhil",
    "Priyanka", "Shruti", "Meera", "Swati", "Rashmi", "Divya", "Tarun", "Harish", "Suresh", "Ramesh"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Mehta", "Iyer", "Nair", "Reddy", "Rao", "Kumar", "Singh",
    "Gupta", "Joshi", "Bhat", "Deshmukh", "Kulkarni", "Chopra", "Malhotra", "Kapoor", "Chatterjee", "Banerjee",
    "Mukherjee", "Das", "Bose", "Sengupta", "Pillai", "Menon", "Chauhan", "Yadav", "Pandey", "Mishra",
    "Shukla", "Trivedi", "Saxena", "Agarwal", "Bansal", "Garg", "Jain", "Bhattacharya", "Choudhury", "Thakur"
]

DEPARTMENTS = [
    "Computer Science",
    "Information Technology",
    "Electronics & Communication",
    "Mechanical Engineering",
    "Civil Engineering",
    "Electrical Engineering"
]


def generate_500_students_csv(output_file: str = "sample_500_students.csv"):
    random.seed(42)  # For reproducible sample data
    rows = []

    for i in range(1, 501):
        stu_id = f"STU2026{i:03d}"
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        name = f"{fname} {lname}"
        dept = random.choice(DEPARTMENTS)
        year = random.randint(1, 4)
        password = stu_id  # Default password is their student ID
        # Make ~96% active, ~4% inactive for edge-case testing
        is_active = "true" if random.random() > 0.04 else "false"

        rows.append({
            "student_id": stu_id,
            "name": name,
            "department": dept,
            "year": year,
            "password": password,
            "is_active": is_active
        })

    with open(output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["student_id", "name", "department", "year", "password", "is_active"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} student records into '{output_file}'.")


if __name__ == "__main__":
    generate_500_students_csv()
