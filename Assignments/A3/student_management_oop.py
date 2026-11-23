"""Python OOP Assignment: Student Management System (Sections A-H)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

RECORD_FILE = Path(__file__).with_name('students.txt')
student_count = 0  # global variable, shared by functions


# D: Base class and inheritance
class Person:
    def __init__(self, name):
        self.name = name

    def show_name(self):
        print(f'Name: {self.name}')

    def display_info(self):
        print(f'Person: {self.name}')


# C, D, E, F: Student inherits Person
class Student(Person):
    school_name = 'City College'  # class variable, shared by students

    class ContactInfo:  # nested class
        def __init__(self, email, phone):
            self.email = email
            self.phone = phone

        def __str__(self):
            return f'{self.email}, {self.phone}'

    def __init__(self, name, roll_number, marks, contact=None):
        super().__init__(name)  # reuse Person constructor
        self.roll_number = roll_number  # public attribute
        self._marks = self.validate_marks(marks)  # protected by convention
        self.__status = 'Active'  # name-mangled private attribute
        self.contact = contact
        self.report = ReportCard(self._marks)  # composition: owned component

    @staticmethod
    def validate_marks(marks):
        if not isinstance(marks, (list, tuple)) or not marks:
            raise ValueError('Marks must be a non-empty list or tuple.')
        checked = []
        for mark in marks:
            if isinstance(mark, bool) or not isinstance(mark, (int, float)):
                raise ValueError('Marks must be numbers.')
            if not 0 <= mark <= 100:
                raise ValueError('Marks must be between 0 and 100.')
            checked.append(float(mark))
        return checked

    @classmethod
    def update_school_name(cls, new_name):
        cls.school_name = new_name

    @property
    def marks(self):
        return self._marks.copy()

    def calculate_average(self):
        return sum(self._marks) / len(self._marks)

    def display_details(self):
        print(f'{self.name} (Roll: {self.roll_number}), marks: {self._marks}, '
              f'average: {self.calculate_average():.2f}, grade: {determine_grade(self.calculate_average())}')

    def display_info(self):  # overriding
        print(f'Student: {self.name}, roll {self.roll_number}')

    def get_status(self):
        return self.__status

    def __str__(self):
        return f'Student({self.name}, roll={self.roll_number})'

    def __len__(self):
        return len(self._marks)

    def __del__(self):
        # Demonstration only: never rely on __del__ to save files or close resources.
        pass


class ReportCard:
    """Composition: a student creates and owns this report component."""
    def __init__(self, marks):
        self.marks = marks.copy()

    def summary(self):
        return f'{len(self.marks)} subjects, total {sum(self.marks):.1f}'


class GraduateStudent(Student):  # multilevel: Person -> Student -> GraduateStudent
    def __init__(self, name, roll_number, marks, research_topic):
        super().__init__(name, roll_number, marks)
        self.research_topic = research_topic


class Teacher(Person):  # hierarchical: Person -> Student and Person -> Teacher
    def __init__(self, name, subject):
        super().__init__(name)
        self.subject = subject

    def display_info(self):
        print(f'Teacher: {self.name}, teaches {self.subject}')


class SportsMember:
    def sport(self):
        return 'Cricket'


class StudentAthlete(Student, SportsMember):  # multiple inheritance
    pass


class Department:  # aggregation: students exist independently
    def __init__(self, name):
        self.name = name
        self.students = []

    def add_student(self, student):
        self.students.append(student)


class Marks:
    def __init__(self, values):
        self.values = Student.validate_marks(values)

    def __add__(self, other):
        if not isinstance(other, Marks):
            return NotImplemented
        return Marks(self.values + other.values)

    def __str__(self):
        return f'Marks{self.values}'

    def __len__(self):
        return len(self.values)


class Record(ABC):
    @abstractmethod
    def display(self):
        pass


class StudentRecord(Record):
    def __init__(self, student):
        self.student = student

    def display(self):
        self.student.display_details()


class TemporaryRecord:
    pass  # placeholder for future features


@dataclass
class Course:
    course_name: str
    course_code: str
    credit_hours: int


# A: functions, arguments, scope, functional tools

def add_student(collection, name, roll_number, marks, enrolled=True):
    """Positional, keyword, and default argument examples."""
    global student_count
    local_message = f'Adding {name}'  # local variable: only in this function
    print(local_message)
    if enrolled:
        student = Student(name, roll_number, marks)
        collection.append(student)
        student_count += 1  # global variable updated here
        return student
    return None


def calculate_average(marks):
    checked = Student.validate_marks(marks)
    return sum(checked) / len(checked)


def determine_grade(average):
    def within_range(value):  # nested helper: used only inside this function
        return 0 <= value <= 100

    if not within_range(average):
        raise ValueError('Average must be between 0 and 100.')
    if average >= 80:
        return 'A'
    elif average >= 70:
        return 'B'
    elif average >= 60:
        return 'C'
    elif average >= 50:
        return 'D'
    return 'Fail'


def display_student_details(student):
    student.display_details()


def display_person(person):  # F: dynamic polymorphism, no type checking
    person.display_info()


# B: file handling and exceptions

def save_students(students, path=RECORD_FILE):
    with open(path, 'w', encoding='utf-8') as file:
        for student in students:
            values = ','.join(f'{mark:g}' for mark in student.marks)
            file.write(f'{student.roll_number}|{student.name}|{values}\n')


def read_students(path=RECORD_FILE):
    try:
        with open(path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
    except FileNotFoundError:
        print(f'File not found: {path.name}')
        return []
    else:  # runs if no exception occurred
        print(f'Read {len(lines)} record(s) from {path.name}:')
        for line in lines:
            print(' ', line.strip())
        return lines
    finally:  # always runs; with already closes the file
        print('File read attempt finished.')


def parse_mark(text):
    try:
        value = float(text)
        Student.validate_marks([value])
    except ValueError as error:
        print(f'Invalid marks input {text!r}: {error}')
        return None
    else:
        return value
    finally:
        print('Validation attempt finished.')


def main():
    print('=== PYTHON OOP: STUDENT MANAGEMENT SYSTEM ===')
    students = []

    print('\nA. FUNCTIONS AND FUNCTIONAL PROGRAMMING')
    first = add_student(students, 'Adnan', '101', [85, 90, 78])  # positional
    second = add_student(collection=students, name='Sara', roll_number='102',
                         marks=[45, 65, 55], enrolled=True)  # keyword + default
    print('Student count (global):', student_count)
    print('Average:', calculate_average(first.marks))
    print('Grade:', determine_grade(first.calculate_average()))
    square = lambda number: number ** 2
    print('Square of 6:', square(6))
    print('Marks out of 10:', list(map(lambda mark: mark / 10, first.marks)))
    print('Students with average >= 50:',
          [student.name for student in filter(lambda s: s.calculate_average() >= 50, students)])

    print('\nB. FILE AND EXCEPTION HANDLING')
    read_students(RECORD_FILE.with_name('missing_students_example.txt'))
    save_students(students)
    read_students()
    parse_mark('abc')
    parse_mark('120')
    print('Valid mark:', parse_mark('75'))
    print('Modes: r=read, w=write/replace, a=append, x=create only if absent.')

    print('\nC. CLASSES AND OBJECTS')
    Student.update_school_name('National College')
    print('Shared school name:', first.school_name, second.school_name)
    display_student_details(first)
    print('Public roll:', first.roll_number, '| protected marks:', first._marks)
    print('Private status via method:', first.get_status())
    print('Mangled attribute example:', first._Student__status)
    print('Student __str__:', str(first), '| __len__:', len(first))

    print('\nD. INHERITANCE AND MRO')
    graduate = GraduateStudent('Bilal', '103', [88, 91], 'Machine Learning')
    teacher = Teacher('Mr. Ahmed', 'Python')
    athlete = StudentAthlete('Hamza', '104', [72, 80])
    graduate.show_name()
    print('Graduate research:', graduate.research_topic)
    print('Student athlete sport:', athlete.sport())
    print('StudentAthlete MRO:', [cls.__name__ for cls in StudentAthlete.mro()])

    print('\nE. CLASS RELATIONSHIPS')
    department = Department('Computer Science')
    department.add_student(first)
    department.add_student(second)
    print('Aggregation:', department.name, 'has', [s.name for s in department.students])
    print('Association:', first.name, 'is taught by', teacher.name)
    print('Composition:', first.name, 'report:', first.report.summary())
    first.contact = Student.ContactInfo('adnan@example.com', '0300-0000000')
    print('Nested ContactInfo:', first.contact)

    print('\nF. POLYMORPHISM AND OPERATOR OVERLOADING')
    for person in [first, second, teacher]:
        display_person(person)
    combined = Marks([80, 90]) + Marks([70, 85])
    print('Combined marks:', combined, '| count:', len(combined))

    print('\nG. ABSTRACT, EMPTY AND DATA CLASSES')
    StudentRecord(first).display()
    print('Empty class object:', type(TemporaryRecord()).__name__)
    course1 = Course('Python', 'CS101', 3)
    course2 = Course('OOP', 'CS102', 4)
    print('Courses:', course1, course2)
    try:
        Record()
    except TypeError:
        print('Cannot create Record directly: display() is abstract.')

    print('\nH. INTEGRATION AND TESTING')
    print('Students:', len(students), '| Teachers:', 1)
    print('Valid data accepted; invalid marks and missing file handled.')
    print('Saved file:', RECORD_FILE.name)
    print('Program completed successfully.')


if __name__ == '__main__':
    main()

# EXPLANATIONS (A-H)
# A: Local variables exist inside a function; global variables exist at module
#    level. Nested functions group helpers with the function that needs them.
# B: try contains risky code; except handles errors; else runs on success;
#    finally runs whether or not an exception occurred. with closes files safely.
# C: __init__ initializes a new object. __del__ may run during garbage
#    collection but its timing is unreliable. _marks is protected by convention;
#    __status becomes _Student__status through name mangling, not true security.
# D: Inheritance reuses code. super() calls parent functionality. MRO determines
#    the order Python searches classes for methods; .mro() displays this order.
# E: Association is a general link; aggregation refers to independent objects;
#    composition means one object owns another component's lifecycle.
# F: Overriding replaces an inherited method. Operator overloading gives + etc.
#    custom meaning. Python does not use signature-based method overloading;
#    default arguments or *args can provide similar flexibility.
# G: Regular classes define general behavior; abstract classes specify required
#    methods; dataclasses generate __init__, __repr__, and equality automatically.
