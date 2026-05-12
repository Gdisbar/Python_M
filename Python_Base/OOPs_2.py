# Python Inheritance & Polymorphism for Java Developers

# =============================================================================
# 1. SINGLE INHERITANCE
# =============================================================================

class Vehicle:
    """Base class - equivalent to Java superclass"""
    
    def __init__(self, brand, model, year):
        self.brand = brand
        self.model = model
        self.year = year
        self.is_running = False
    
    def start(self):
        """Method that can be overridden"""
        self.is_running = True
        return f"{self.brand} {self.model} is starting..."
    
    def stop(self):
        self.is_running = False
        return f"{self.brand} {self.model} has stopped"
    
    def get_info(self):
        return f"{self.year} {self.brand} {self.model}"

class Car(Vehicle):  # Single inheritance - Car extends Vehicle
    """
    Key differences from Java:
    - Python: class Car(Vehicle):
    - Java: class Car extends Vehicle
    - No need for explicit 'extends' keyword
    """
    
    def __init__(self, brand, model, year, doors):
        # Call parent constructor using super()
        super().__init__(brand, model, year)  # Like super() in Java
        self.doors = doors
    
    def start(self):
        """Method overriding - like @Override in Java"""
        # Call parent method and extend it
        parent_msg = super().start()
        return f"{parent_msg} Car engine started with key."
    
    def honk(self):
        """Car-specific method"""
        return f"{self.brand} {self.model} says: Beep beep!"

# Usage
car = Car("Toyota", "Camry", 2023, 4)
print(car.get_info())  # Inherited method
print(car.start())     # Overridden method
print(car.honk())      # Car-specific method

# =============================================================================
# 2. MULTILEVEL INHERITANCE
# =============================================================================

class ElectricCar(Car):  # ElectricCar inherits from Car, which inherits from Vehicle
    """
    Multilevel inheritance: ElectricCar -> Car -> Vehicle
    Similar to Java's inheritance chain
    """
    
    def __init__(self, brand, model, year, doors, battery_capacity):
        super().__init__(brand, model, year, doors)
        self.battery_capacity = battery_capacity
        self.charge_level = 100
    
    def start(self):
        """Override start method again"""
        if self.charge_level > 0:
            self.is_running = True
            return f"{self.brand} {self.model} electric motor started silently. Battery: {self.charge_level}%"
        else:
            return f"{self.brand} {self.model} cannot start - battery empty!"
    
    def charge(self, amount):
        """ElectricCar-specific method"""
        self.charge_level = min(100, self.charge_level + amount)
        return f"Charged to {self.charge_level}%"

# Usage
tesla = ElectricCar("Tesla", "Model 3", 2023, 4, 75)
print(tesla.get_info())  # From Vehicle (grandparent)
print(tesla.honk())      # From Car (parent)
print(tesla.start())     # From ElectricCar (overridden)
print(tesla.charge(20))  # ElectricCar-specific

# =============================================================================
# 3. HIERARCHICAL INHERITANCE
# =============================================================================

class Motorcycle(Vehicle):  # Another child of Vehicle
    """
    Hierarchical inheritance: Multiple classes inherit from same parent
    Vehicle -> Car
    Vehicle -> Motorcycle
    Vehicle -> Truck
    """
    
    def __init__(self, brand, model, year, engine_size):
        super().__init__(brand, model, year)
        self.engine_size = engine_size
    
    def start(self):
        """Override start method"""
        parent_msg = super().start()
        return f"{parent_msg} Motorcycle engine roars to life!"
    
    def wheelie(self):
        """Motorcycle-specific method"""
        if self.is_running:
            return f"{self.brand} {self.model} does a wheelie!"
        return "Can't do wheelie - motorcycle not running"

class Truck(Vehicle):  # Another child of Vehicle
    """Another sibling class"""
    
    def __init__(self, brand, model, year, payload_capacity):
        super().__init__(brand, model, year)
        self.payload_capacity = payload_capacity
    
    def start(self):
        """Override start method"""
        parent_msg = super().start()
        return f"{parent_msg} Truck diesel engine rumbles!"
    
    def load_cargo(self, weight):
        """Truck-specific method"""
        if weight <= self.payload_capacity:
            return f"Loaded {weight}kg cargo successfully"
        return f"Cannot load {weight}kg - exceeds capacity of {self.payload_capacity}kg"

# Usage
bike = Motorcycle("Harley", "Sportster", 2023, 1200)
truck = Truck("Ford", "F-150", 2023, 1000)

print(bike.start())
print(bike.wheelie())
print(truck.start())
print(truck.load_cargo(800))

# =============================================================================
# 4. ADVANCED super() USAGE
# =============================================================================

class Animal:
    def __init__(self, name, species):
        self.name = name
        self.species = species
        print(f"Animal.__init__ called for {name}")
    
    def speak(self):
        return f"{self.name} makes a sound"

class Mammal(Animal):
    def __init__(self, name, species, fur_color):
        super().__init__(name, species)  # Call Animal.__init__
        self.fur_color = fur_color
        print(f"Mammal.__init__ called for {name}")
    
    def speak(self):
        return f"{self.name} makes a mammalian sound"

class Dog(Mammal):
    def __init__(self, name, breed, fur_color):
        # Call Mammal.__init__, which calls Animal.__init__
        super().__init__(name, "Canis lupus", fur_color)
        self.breed = breed
        print(f"Dog.__init__ called for {name}")
    
    def speak(self):
        """Override speak method"""
        return f"{self.name} barks: Woof!"
    
    def describe(self):
        """Use super() to call parent method and extend it"""
        parent_description = super().speak()
        return f"{parent_description} - specifically, {self.speak()}"

# Usage
dog = Dog("Buddy", "Golden Retriever", "Golden")
print(dog.speak())
print(dog.describe())

# =============================================================================
# 5. METHOD OVERRIDING & POLYMORPHISM
# =============================================================================

class Shape:
    """Base class for demonstrating polymorphism"""
    
    def __init__(self, color):
        self.color = color
    
    def area(self):
        """Abstract-like method to be overridden"""
        raise NotImplementedError("Subclass must implement area()")
    
    def describe(self):
        return f"This is a {self.color} shape"

class Circle(Shape):
    def __init__(self, color, radius):
        super().__init__(color)
        self.radius = radius
    
    def area(self):
        """Override area method"""
        return 3.14159 * self.radius ** 2
    
    def describe(self):
        """Override describe method"""
        return f"This is a {self.color} circle with radius {self.radius}"

class Rectangle(Shape):
    def __init__(self, color, width, height):
        super().__init__(color)
        self.width = width
        self.height = height
    
    def area(self):
        """Override area method"""
        return self.width * self.height
    
    def describe(self):
        """Override describe method"""
        return f"This is a {self.color} rectangle ({self.width}x{self.height})"

class Triangle(Shape):
    def __init__(self, color, base, height):
        super().__init__(color)
        self.base = base
        self.height = height
    
    def area(self):
        """Override area method"""
        return 0.5 * self.base * self.height

# Polymorphism in action
def print_shape_info(shape):
    """
    Polymorphic function - works with any Shape subclass
    Similar to Java polymorphism but more flexible
    """
    print(f"Shape: {shape.describe()}")
    print(f"Area: {shape.area():.2f}")
    print("-" * 30)

# Create different shapes
shapes = [
    Circle("red", 5),
    Rectangle("blue", 4, 6),
    Triangle("green", 8, 3)
]

# Polymorphic behavior - same method call, different implementations
for shape in shapes:
    print_shape_info(shape)

# =============================================================================
# 6. DUCK TYPING & DYNAMIC TYPING
# =============================================================================

class Duck:
    """Duck class for demonstrating duck typing"""
    
    def quack(self):
        return "Quack quack!"
    
    def fly(self):
        return "Duck flies away"

class Goose:
    """Goose class - not related to Duck but has same methods"""
    
    def quack(self):
        return "Honk honk!"
    
    def fly(self):
        return "Goose flies majestically"

class Robot:
    """Robot class - completely unrelated but has same interface"""
    
    def quack(self):
        return "Beep beep! (robot quack)"
    
    def fly(self):
        return "Robot activates jetpack"

class Cat:
    """Cat class - missing fly method"""
    
    def quack(self):
        return "Meow? (confused cat)"
    
    # No fly method - will cause AttributeError

def make_it_quack_and_fly(bird):
    """
    Duck typing: "If it walks like a duck and quacks like a duck, it's a duck"
    
    Key differences from Java:
    - No interface declaration needed
    - No implements keyword
    - Runtime checking instead of compile-time
    - More flexible but less safe than Java interfaces
    """
    print(f"Sound: {bird.quack()}")
    print(f"Flight: {bird.fly()}")
    print("-" * 20)

# Duck typing in action
animals = [Duck(), Goose(), Robot()]

for animal in animals:
    make_it_quack_and_fly(animal)

# This will work for quack but fail for fly
cat = Cat()
try:
    make_it_quack_and_fly(cat)
except AttributeError as e:
    print(f"Duck typing failed: {e}")

# =============================================================================
# 7. DYNAMIC TYPING EXAMPLES
# =============================================================================

def process_data(data):
    """
    Dynamic typing example - same function works with different types
    Java equivalent would need method overloading or generics
    """
    if hasattr(data, 'upper'):  # Check if it's string-like
        return f"Processing text: {data.upper()}"
    elif hasattr(data, '__iter__') and not isinstance(data, str):  # Check if it's iterable
        return f"Processing collection: {len(data)} items"
    elif hasattr(data, '__add__'):  # Check if it supports addition
        return f"Processing number: {data + 10}" # type: ignore
    else:
        return f"Processing unknown type: {type(data)}"

# Dynamic typing in action
test_data = [
    "hello world",
    [1, 2, 3, 4, 5],
    42,
    {"key": "value"}
]

for data in test_data:
    print(process_data(data))

# =============================================================================
# 8. COMPARISON WITH JAVA
# =============================================================================

# """
# KEY DIFFERENCES FROM JAVA:

# 1. INHERITANCE SYNTAX:
#    - Python: class Child(Parent):
#    - Java: class Child extends Parent
#    - Python: Multiple inheritance supported
#    - Java: Single inheritance only (interfaces for multiple)

# 2. METHOD OVERRIDING:
#    - Python: No @Override annotation needed
#    - Java: @Override annotation recommended
#    - Python: Runtime method resolution
#    - Java: Compile-time method resolution

# 3. POLYMORPHISM:
#    - Python: Duck typing - structure matters, not inheritance
#    - Java: Interface/inheritance-based polymorphism
#    - Python: More flexible, less safe
#    - Java: More restrictive, safer

# 4. SUPER() USAGE:
#    - Python: super() without parameters (Python 3)
#    - Java: super() calls parent constructor
#    - Python: Can call any parent method
#    - Java: More structured approach

# 5. DYNAMIC vs STATIC:
#    - Python: Duck typing allows runtime flexibility
#    - Java: Static typing requires compile-time contracts
#    - Python: "Ask for forgiveness, not permission"
#    - Java: "Better safe than sorry"

# ADVANTAGES OF PYTHON APPROACH:
# - More flexible and concise
# - Less boilerplate code
# - Easier to prototype and experiment
# - Duck typing allows for creative solutions

# ADVANTAGES OF JAVA APPROACH:
# - Compile-time error detection
# - Better IDE support and refactoring
# - Clearer contracts and interfaces
# - More predictable behavior
# """