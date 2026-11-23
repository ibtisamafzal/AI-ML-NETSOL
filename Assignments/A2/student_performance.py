
# Python Basics Assignment
# Student Performance and Result Management System
# Student: Muhammad Ibtisam Afzal

# Each subject is out of 100 marks.
# Passing requires at least 50 marks in every subject.
# Distinction requires 80% or above and passing all subjects.

# --------------------------------------------------
# A. VALUES, VARIABLES, EXPRESSIONS, AND OPERATORS
# --------------------------------------------------

print("=" * 55)
print("STUDENT PERFORMANCE AND RESULT MANAGEMENT SYSTEM")
print("=" * 55)

student_name = "Ali Ahmad"       # str
student_age = 20                # int
enrolled = True                # bool
sample_mark = 85.5             # float

subjects = [
    "English", "Mathematics", "Computer Science",
    "Physics", "Urdu"
]

print("\nA. VARIABLES AND DATA TYPES")
print("Name:", student_name, "-", type(student_name))
print("Age:", student_age, "-", type(student_age))
print("Enrolled:", enrolled, "-", type(enrolled))
print("Sample Mark:", sample_mark, "-", type(sample_mark))

# Value: A piece of data, such as 20 or "Ali".
# Variable: A name used to store a value, e.g. age = 20.
# Expression: A calculation that produces a value, e.g. 10 + 5.
# Statement: An instruction, e.g. age = 20 or print(age).
# Keyword: A reserved Python word, e.g. if, for, while.

# --------------------------------------------------
# B. STRINGS, INPUT, TYPE CASTING, AND COMMENTS
# --------------------------------------------------

print("\nB. ENTER STUDENT INFORMATION")

name = input("Enter student name: ").strip()

while not name:
    print("Name cannot be empty.")
    name = input("Enter student name: ").strip()

print("Uppercase:", name.upper())
print("Lowercase:", name.lower())

# input() returns a string.
# int() and float() convert strings into numeric values.

while True:
    try:
        age = int(input("Enter student age: "))
        if age <= 0:
            print("Please enter a valid age.")
            continue
        break
    except ValueError:
        print("Age must be a whole number.")

roll_number = input("Enter roll number: ").strip()

while not roll_number:
    print("Roll number cannot be empty.")
    roll_number = input("Enter roll number: ").strip()

while True:
    try:
        admission_year = int(input("Enter admission year: "))
        if admission_year < 1900 or admission_year > 2100:
            print("Enter a valid admission year.")
            continue
        break
    except ValueError:
        print("Please enter a valid year.")

# --------------------------------------------------
# C. PYTHON DATA STRUCTURES
# --------------------------------------------------

print("\nC. PYTHON DATA STRUCTURES")

# LIST: Ordered, changeable, allows duplicates.
subject_list = [
    "English", "Mathematics", "Computer Science",
    "Physics", "Urdu"
]

print("Original subjects:", subject_list)

# Add a subject.
subject_list.append("Biology")
print("After adding:", subject_list)

# Update an existing subject.
subject_list[4] = "Pakistan Studies"
print("After updating:", subject_list)

# Remove a subject.
subject_list.remove("Biology")
print("After removing:", subject_list)

# TUPLE: Ordered and cannot be changed.
# Suitable for roll number and admission year.
student_tuple = (roll_number, admission_year)
print("Student tuple:", student_tuple)

# SET: Stores unique values without duplicates.
unique_subjects = {
    "English", "Mathematics", "Physics",
    "English", "Physics"
}
print("Unique subjects:", sorted(unique_subjects))

# DICTIONARY: Stores data in key-value pairs.
student_dict = {
    "name": name,
    "age": age,
    "marks": {}
}

# Add a new key-value pair.
student_dict["roll_number"] = roll_number
print("Student dictionary:", student_dict)

# --------------------------------------------------
# D. CONDITIONAL EXECUTION
# E. LOOPS AND CONTROL STATEMENTS
# --------------------------------------------------

print("\nD & E. ENTER SUBJECT MARKS")

marks = {}

# for loop with enumerate()
for number, subject in enumerate(subject_list, start=1):
    print(f"\nSubject {number}: {subject}")

    # while loop keeps asking until valid input is given.
    while True:
        value = input(
            f"Enter marks for {subject} (0-100), or Q to stop: "
        ).strip()

        # break stops the loop when the student chooses Q.
        if value.lower() == "q":
            print("Mark entry stopped.")
            break

        try:
            mark = float(value)

            if mark < 0 or mark > 100:
                print("Marks must be between 0 and 100.")
                continue

            marks[subject] = mark
            break

        except ValueError:
            print("Invalid input. Enter a number.")
            continue

    if value.lower() == "q":
        break

# Save marks in the dictionary.
student_dict["marks"] = marks

# Calculate the result only if all five marks are entered.
if len(marks) == len(subject_list):

    total_marks = sum(marks.values())
    average_marks = total_marks / len(marks)
    percentage = (total_marks / (len(marks) * 100)) * 100

    # Comparison and logical operators
    passed = percentage >= 50 and all(
        mark >= 50 for mark in marks.values()
    )

    # if, elif, else for grades
    if not passed:
        grade = "Fail"
    elif percentage >= 80:
        grade = "A"
    elif percentage >= 70:
        grade = "B"
    elif percentage >= 60:
        grade = "C"
    else:
        grade = "D"

    # Nested conditional
    if passed:
        if percentage >= 80:
            distinction = "Yes"
        else:
            distinction = "No"
    else:
        distinction = "No"

    # Ternary expression
    eligibility = "Eligible" if passed else "Not Eligible"

    print("\n" + "=" * 55)
    print("STUDENT PERFORMANCE REPORT")
    print("=" * 55)

    print(f"Name: {name}")
    print(f"Age: {age}")
    print(f"Roll Number: {roll_number}")
    print(f"Admission Year: {admission_year}")

    print("\nSubject-wise Marks")

    for number, (subject, mark) in enumerate(
        marks.items(), start=1
    ):
        print(f"{number}. {subject}: {mark:.2f}/100")

    print(f"\nTotal Marks: {total_marks:.2f}/500")
    print(f"Average Marks: {average_marks:.2f}")
    print(f"Percentage: {percentage:.2f}%")
    print(f"Grade: {grade}")
    print(f"Result: {'Pass' if passed else 'Fail'}")
    print(f"Distinction: {distinction}")
    print(f"Pass Eligibility: {eligibility}")

    # Store calculated results.
    student_dict["total"] = total_marks
    student_dict["average"] = average_marks
    student_dict["percentage"] = percentage
    student_dict["grade"] = grade
    student_dict["result"] = "Pass" if passed else "Fail"

    # Retrieve marks from the dictionary.
    print("\nMarks from dictionary:", student_dict["marks"])

    # Nested loops: student and subject table.
    print("\nSTUDENT AND SUBJECT TABLE")
    students = [student_dict]

    for student in students:
        print("Student:", student["name"])
        for subject, mark in student["marks"].items():
            print(f"  {subject}: {mark}")

    # Save the record to a text file.
    with open("student_records.txt", "a", encoding="utf-8") as file:
        file.write(f"Name: {name}\n")
        file.write(f"Roll Number: {roll_number}\n")
        file.write(f"Marks: {marks}\n")
        file.write(f"Percentage: {percentage:.2f}%\n")
        file.write(f"Grade: {grade}\n")
        file.write(f"Result: {student_dict['result']}\n")
        file.write("-" * 40 + "\n")

    print("\nStudent record saved to student_records.txt")

else:
    print("\nResult not calculated because some marks are missing.")

# Explanation:
# if checks the first condition.
# elif checks another condition if previous ones are false.
# else runs when none of the conditions are true.
# The order matters because Python checks from top to bottom.
# For example, checking >= 50 before >= 80 would give
# an A-grade student a D instead.

# --------------------------------------------------
# E. ADDITIONAL LOOP EXAMPLES
# --------------------------------------------------

print("\nE. LOOP EXAMPLES")

# for loop displays all subjects.
for subject in subject_list:
    print(subject)

# enumerate() adds serial numbers.
for index, subject in enumerate(subject_list, 1):
    print(index, subject)

# pass is a placeholder that does nothing.
# It is useful when code will be added later.
for subject in subject_list:
    if subject == "Physics":
        pass

# continue skips the current iteration.
sample_marks = [45, 75, -10, 90]
    
for mark in sample_marks:
    if mark < 0:
        continue

    if mark == 90:
        print("Stopping because mark 90 was found.")
        break

    print("Before stopping:", mark)

# --------------------------------------------------
# F. LIST COMPREHENSION AND ITERATORS
# --------------------------------------------------

print("\nF. LIST COMPREHENSION AND ITERATORS")

marks_list = [35, 78, 45, 90, 62, 28, 85]

# Marks greater than or equal to 50.
passing_marks = [mark for mark in marks_list if mark >= 50]
print("Passing marks:", passing_marks)

# Squares of even numbers from 1 to 20.
even_squares = [n ** 2 for n in range(1, 21) if n % 2 == 0]
print("Squares of even numbers:", even_squares)

# An iterable can be used in a for loop.
# An iterator remembers its current position.
# iter() creates an iterator from a list.
# next() retrieves the next element.

numbers = [10, 20, 30]
number_iterator = iter(numbers)

print("First:", next(number_iterator))
print("Second:", next(number_iterator))
print("Third:", next(number_iterator))

# Calling next() again raises StopIteration.
try:
    print(next(number_iterator))
except StopIteration:
    print("Iterator has no more elements.")

# --------------------------------------------------
# G. CODE ANALYSIS AND DEBUGGING
# --------------------------------------------------

print("\nG. CODE ANALYSIS AND DEBUGGING")

marks = [45, 80, 32, 90, 65]
passed_marks = []

for mark in marks:
    if mark < 50:
        continue
    passed_marks.append(mark)

print("Passed marks:", passed_marks)
print("Number of passed marks:", len(passed_marks))
print("Average:", sum(passed_marks) / len(passed_marks))

# Original output:
# [80, 90, 65]
# 3
# 78.33333333333333

# continue skips marks below 50.
# If continue is replaced by break, the loop stops
# at the first mark (45), leaving the list empty.
# Dividing by its length would cause ZeroDivisionError.

# If all marks are below 50, passed_marks is empty.
# We should check the list before calculating average.

all_failed = [20, 30, 40]
passed = [mark for mark in all_failed if mark >= 50]

if len(passed) > 0:
    print("Average:", sum(passed) / len(passed))
else:
    print("No passing marks. Average cannot be calculated.")

# Rewrite the original loop using list comprehension.
passed_comprehension = [mark for mark in marks if mark >= 50]
print("List comprehension result:", passed_comprehension)

# --------------------------------------------------
# THREE TEST CASES
# --------------------------------------------------

print("\n" + "=" * 55)
print("TESTING WITH THREE SETS OF MARKS")
print("=" * 55)

test_cases = [
    [90, 85, 88, 92, 80],
    [55, 60, 65, 70, 75],
    [95, 90, 40, 85, 90]
]

for test_number, test_marks in enumerate(test_cases, 1):

    total = sum(test_marks)
    percentage = total / 500 * 100

    passed = percentage >= 50 and all(
        mark >= 50 for mark in test_marks
    )

    if not passed:
        grade = "Fail"
    elif percentage >= 80:
        grade = "A"
    elif percentage >= 70:
        grade = "B"
    elif percentage >= 60:
        grade = "C"
    else:
        grade = "D"

    print(f"\nTest Case {test_number}")
    print("Marks:", test_marks)
    print(f"Total: {total}/500")
    print(f"Percentage: {percentage:.2f}%")
    print("Grade:", grade)
    print("Result:", "Pass" if passed else "Fail")

print("\nProgram completed successfully.")
