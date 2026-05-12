# # Python OOP Concepts for Java Developers

# =============================================================================
# 1. CLASS AND OBJECT
# =============================================================================

# class BankAccount:
#     """
#     Key differences from Java:
#     - No explicit 'public class' declaration
#     - __init__ is the constructor (not the class name)
#     - 'self' is explicit (like 'this' in Java, but must be declared)
#     - No need to declare instance variables beforehand
#     """
    
#     def __init__(self, account_number, initial_balance=0.0):
#         """
#         Constructor method - equivalent to Java constructor
#         - __init__ is called when object is created
#         - self is the first parameter (equivalent to 'this' in Java)
#         - Can have default parameters (initial_balance=0.0)
#         """
#         self.account_number = account_number    # Instance variable
#         self.balance = initial_balance          # Instance variable
#         self.transaction_count = 0              # Instance variable
    
#     def deposit(self, amount):
#         """Instance method - operates on specific object instance"""
#         self.balance += amount
#         self.transaction_count += 1
#         return self.balance

# # Object creation (simpler than Java - no 'new' keyword)
# account1 = BankAccount("ACC001", 1000.0)
# account2 = BankAccount("ACC002")  # Uses default balance

# print(f"Account 1 balance: ${account1.balance}")
# print(f"Account 2 balance: ${account2.balance}")

# account1.deposit(500)
# print(f"After deposit: ${account1.balance}")

# =============================================================================
# 2. INSTANCE METHODS vs CLASS METHODS vs STATIC METHODS
# =============================================================================

class Employee:
    # Class variable (shared by all instances)
    company_name = "TechCorp"
    employee_count = 0
    
    def __init__(self, name, salary):
        self.name = name
        self.salary = salary
        Employee.employee_count += 1
    
    # INSTANCE METHOD
    def get_details(self):
        """
        Instance method - has access to 'self' and instance variables
        Similar to regular methods in Java
        """
        return f"Employee: {self.name}, Salary: ${self.salary}"
    
    def give_raise(self, percentage):
        """Another instance method"""
        self.salary *= (1 + percentage / 100)
        return self.salary
    
    # CLASS METHOD
    @classmethod
    def get_company_info(cls):
        """
        Class method - has access to 'cls' (the class itself)
        Similar to static methods in Java but can access class variables
        - Use when you need to access/modify class variables
        - 'cls' refers to the class (like Class.forName() in Java)
        """
        return f"Company: {cls.company_name}, Total Employees: {cls.employee_count}"
    
    @classmethod
    def create_intern(cls, name):
        """
        Class method used as alternative constructor
        Common pattern in Python (like factory methods in Java)
        """
        return cls(name, 30000)  # Create employee with fixed intern salary
    
    # STATIC METHOD
    @staticmethod
    def calculate_annual_salary(monthly_salary):
        """
        Static method - no access to 'self' or 'cls'
        Exactly like static methods in Java
        - Use for utility functions related to the class
        - Could be a regular function, but belongs conceptually to the class
        """
        return monthly_salary * 12
    
    @staticmethod
    def is_valid_salary(salary):
        """Another static method example"""
        return salary > 0 and salary < 1000000

# Usage examples:
emp1 = Employee("Alice", 5000)
emp2 = Employee("Bob", 6000)

# Instance method calls
print(emp1.get_details())
emp1.give_raise(10)
print(f"After raise: ${emp1.salary}")

# Class method calls (can be called on class or instance)
print(Employee.get_company_info())
print(emp1.get_company_info())  # Same result

# Create employee using class method
intern = Employee.create_intern("Charlie")
print(intern.get_details())

# Static method calls (can be called on class or instance)
annual = Employee.calculate_annual_salary(5000)
print(f"Annual salary: ${annual}")

print(f"Is $50000 valid? {Employee.is_valid_salary(50000)}")

# # =============================================================================
# # 3. ENCAPSULATION
# # =============================================================================

# class Student:
#     """
#     Python encapsulation is different from Java:
#     - No true 'private' keyword
#     - Conventions: _protected, __private
#     - @property decorator for getters/setters
#     """
    
#     def __init__(self, name, age, student_id):
#         self.name = name                    # Public (like Java public)
#         self._age = age                     # Protected (like Java protected)
#         self.__student_id = student_id      # Private (like Java private)
#         self._grades = []                   # Protected list
    
#     # PUBLIC METHOD
#     def add_grade(self, grade):
#         """Public method - can be called from anywhere"""
#         if self._is_valid_grade(grade):
#             self._grades.append(grade)
#         else:
#             raise ValueError("Grade must be between 0 and 100")
    
#     # PROTECTED METHOD (convention - not enforced)
#     def _is_valid_grade(self, grade):
#         """
#         Protected method (single underscore)
#         - Convention: should only be used within class and subclasses
#         - Not enforced by Python (unlike Java)
#         """
#         return 0 <= grade <= 100
    
#     # PRIVATE METHOD (name mangling)
#     def __calculate_gpa(self):
#         """
#         Private method (double underscore)
#         - Name mangling: becomes _Student__calculate_gpa
#         - Harder to access from outside, but not impossible
#         """
#         if not self._grades:
#             return 0.0
#         return sum(self._grades) / len(self._grades)
    
#     # GETTER using @property decorator
#     @property
#     def age(self):
#         """
#         Getter method - equivalent to getAge() in Java
#         Can be accessed like: student.age (not student.age())
#         """
#         return self._age
    
#     # SETTER using @property.setter
#     @age.setter
#     def age(self, value):
#         """
#         Setter method - equivalent to setAge(int age) in Java
#         Can be set like: student.age = 20 (not student.setAge(20))
#         """
#         if value < 0 or value > 150:
#             raise ValueError("Age must be between 0 and 150")
#         self._age = value
    
#     # GETTER for student_id (read-only)
#     @property
#     def student_id(self):
#         """Read-only property - no setter defined"""
#         return self.__student_id
    
#     # GETTER for GPA (computed property)
#     @property
#     def gpa(self):
#         """Computed property - calculated each time it's accessed"""
#         return self.__calculate_gpa()
    
#     # GETTER for grades (returns copy to prevent external modification)
#     @property
#     def grades(self):
#         """Return copy of grades to maintain encapsulation"""
#         return self._grades.copy()

# # Usage examples:
# student = Student("John Doe", 20, "STU001")

# # Public access
# print(f"Student name: {student.name}")
# student.add_grade(85)
# student.add_grade(92)

# # Protected access (works but discouraged)
# print(f"Protected age: {student._age}")

# # Private access (name mangling makes it harder)
# try:
#     print(student.__student_id)  # This will fail
# except AttributeError as e:
#     print(f"Error accessing private attribute: {e}")

# # Access private attribute using name mangling (not recommended)
# print(f"Private student_id via name mangling: {student._Student__student_id}")

# # Using property getters/setters
# print(f"Age via property: {student.age}")
# student.age = 21  # Using setter
# print(f"Updated age: {student.age}")

# # Read-only property
# print(f"Student ID (read-only): {student.student_id}")

# # Computed property
# print(f"Current GPA: {student.gpa:.2f}")

# # Getting grades (returns copy)
# grades = student.grades
# print(f"Grades: {grades}")

# # Try to set invalid age
# try:
#     student.age = -5
# except ValueError as e:
#     print(f"Validation error: {e}")

# # =============================================================================
# # COMPARISON WITH JAVA
# # =============================================================================

# """
# KEY DIFFERENCES FROM JAVA:

# 1. CLASS AND OBJECT:
#    - Python: class ClassName:
#    - Java: public class ClassName
#    - Python: __init__(self, ...)
#    - Java: public ClassName(...)
#    - Python: obj = ClassName()
#    - Java: ClassName obj = new ClassName()

# 2. METHODS:
#    - Python: Explicit 'self' parameter
#    - Java: Implicit 'this' reference
#    - Python: @classmethod, @staticmethod decorators
#    - Java: static keyword for static methods

# 3. ENCAPSULATION:
#    - Python: Convention-based (_protected, __private)
#    - Java: Enforced keywords (private, protected, public)
#    - Python: @property decorator for getters/setters
#    - Java: Explicit getter/setter methods

# 4. FLEXIBILITY:
#    - Python: Dynamic typing, can add attributes at runtime
#    - Java: Static typing, strict structure
#    - Python: Duck typing ("if it walks like a duck...")
#    - Java: Interface/inheritance-based polymorphism
# """