# Python Abstraction with ABC for Java Developers

from abc import ABC, abstractmethod, abstractproperty
from typing import List, Optional

# =============================================================================
# 1. BASIC ABSTRACT BASE CLASS
# =============================================================================

class Animal(ABC):
    """
    Abstract Base Class - equivalent to Java abstract class
    
    Key differences from Java:
    - Python: class Animal(ABC):
    - Java: abstract class Animal
    - Python: Must import ABC from abc module
    - Java: abstract keyword is built-in
    """
    
    def __init__(self, name: str, species: str):
        # Abstract classes can have constructors and instance variables
        self.name = name
        self.species = species
        self._energy = 100
    
    @abstractmethod
    def make_sound(self) -> str:
        """
        Abstract method - must be implemented by subclasses
        
        Equivalent to Java: public abstract String makeSound();
        - @abstractmethod decorator is required
        - Can have implementation (unlike Java abstract methods)
        - Subclasses must override this method
        """
        pass  # This implementation will be overridden
    
    @abstractmethod
    def move(self) -> str:
        """Another abstract method"""
        pass
    
    # Concrete method (has implementation)
    def eat(self, food: str) -> str:
        """
        Concrete method - can be used directly or overridden
        Similar to regular methods in Java abstract classes
        """
        self._energy += 10
        return f"{self.name} eats {food} and gains energy. Energy: {self._energy}"
    
    def sleep(self) -> str:
        """Another concrete method"""
        self._energy = 100
        return f"{self.name} sleeps and restores energy to {self._energy}"

class Dog(Animal):
    """
    Concrete class implementing abstract methods
    Must implement all abstract methods or it will also be abstract
    """
    
    def __init__(self, name: str, breed: str):
        super().__init__(name, "Canis lupus")
        self.breed = breed
    
    def make_sound(self) -> str:
        """Must implement this abstract method"""
        return f"{self.name} barks: Woof! Woof!"
    
    def move(self) -> str:
        """Must implement this abstract method"""
        return f"{self.name} runs on four legs"
    
    def fetch(self, item: str) -> str:
        """Dog-specific method"""
        return f"{self.name} fetches the {item}"

class Bird(Animal):
    """Another concrete implementation"""
    
    def __init__(self, name: str, wingspan: float):
        super().__init__(name, "Aves")
        self.wingspan = wingspan
    
    def make_sound(self) -> str:
        return f"{self.name} chirps: Tweet tweet!"
    
    def move(self) -> str:
        return f"{self.name} flies with {self.wingspan}m wingspan"

# Usage
# animal = Animal("Generic", "Unknown")  # This would raise TypeError!

dog = Dog("Buddy", "Golden Retriever")
bird = Bird("Tweety", 0.3)

print(dog.make_sound())  # Implemented method
print(dog.move())        # Implemented method
print(dog.eat("kibble")) # Inherited concrete method
print(dog.fetch("ball")) # Dog-specific method

print("\n" + "="*50 + "\n")

# =============================================================================
# 2. ABSTRACT PROPERTIES
# =============================================================================

class Shape(ABC):
    """Abstract class with abstract properties"""
    
    def __init__(self, color: str):
        self.color = color
    
    @property
    @abstractmethod
    def area(self) -> float:
        """
        Abstract property - must be implemented as property in subclasses
        
        Java equivalent would be: public abstract double getArea();
        But Python's approach is more elegant with @property
        """
        pass
    
    @property
    @abstractmethod
    def perimeter(self) -> float:
        """Another abstract property"""
        pass
    
    @abstractmethod
    def draw(self) -> str:
        """Abstract method"""
        pass
    
    # Concrete method using abstract properties
    def describe(self) -> str:
        """
        Concrete method that uses abstract properties
        This demonstrates how abstract properties can be used in concrete methods
        """
        return f"This {self.color} shape has area {self.area:.2f} and perimeter {self.perimeter:.2f}"

class Circle(Shape):
    """Concrete implementation with properties"""
    
    def __init__(self, color: str, radius: float):
        super().__init__(color)
        self._radius = radius
    
    @property
    def area(self) -> float:
        """Implement abstract property"""
        return 3.14159 * self._radius ** 2
    
    @property
    def perimeter(self) -> float:
        """Implement abstract property"""
        return 2 * 3.14159 * self._radius
    
    @property
    def radius(self) -> float:
        """Additional property specific to Circle"""
        return self._radius
    
    def draw(self) -> str:
        """Implement abstract method"""
        return f"Drawing a {self.color} circle with radius {self._radius}"

class Rectangle(Shape):
    """Another concrete implementation"""
    
    def __init__(self, color: str, width: float, height: float):
        super().__init__(color)
        self._width = width
        self._height = height
    
    @property
    def area(self) -> float:
        return self._width * self._height
    
    @property
    def perimeter(self) -> float:
        return 2 * (self._width + self._height)
    
    def draw(self) -> str:
        return f"Drawing a {self.color} rectangle ({self._width}x{self._height})"

# Usage
circle = Circle("red", 5)
rectangle = Rectangle("blue", 4, 6)

print(circle.describe())      # Uses concrete method with abstract properties
print(circle.draw())          # Implemented abstract method
print(f"Circle area: {circle.area}")  # Abstract property implemented

print(rectangle.describe())
print(rectangle.draw())

print("\n" + "="*50 + "\n")

# =============================================================================
# 3. MULTIPLE INHERITANCE WITH ABSTRACT CLASSES
# =============================================================================

class Flyable(ABC):
    """
    Abstract class for flying behavior
    Similar to Java interface but can have concrete methods
    """
    
    @abstractmethod
    def fly(self) -> str:
        """Abstract flying method"""
        pass
    
    @abstractmethod
    def land(self) -> str:
        """Abstract landing method"""
        pass
    
    def check_flight_conditions(self) -> str:
        """Concrete method available to all flying objects"""
        return "Checking weather conditions for flight..."

class Swimmable(ABC):
    """Abstract class for swimming behavior"""
    
    @abstractmethod
    def swim(self) -> str:
        """Abstract swimming method"""
        pass
    
    @abstractmethod
    def dive(self) -> str:
        """Abstract diving method"""
        pass
    
    def check_water_conditions(self) -> str:
        """Concrete method"""
        return "Checking water temperature and currents..."

class Duck(Animal, Flyable, Swimmable):
    """
    Multiple inheritance from abstract classes
    Must implement all abstract methods from all parent classes
    
    Java equivalent would require interfaces:
    class Duck extends Animal implements Flyable, Swimmable
    """
    
    def __init__(self, name: str):
        super().__init__(name, "Anas platyrhynchos")
    
    # Implement Animal abstract methods
    def make_sound(self) -> str:
        return f"{self.name} quacks: Quack quack!"
    
    def move(self) -> str:
        return f"{self.name} waddles on land"
    
    # Implement Flyable abstract methods
    def fly(self) -> str:
        return f"{self.name} flies through the air"
    
    def land(self) -> str:
        return f"{self.name} lands gracefully on water"
    
    # Implement Swimmable abstract methods
    def swim(self) -> str:
        return f"{self.name} swims on the surface"
    
    def dive(self) -> str:
        return f"{self.name} dives underwater for food"

# Usage
duck = Duck("Donald")

# Animal methods
print(duck.make_sound())
print(duck.eat("bread"))

# Flyable methods
print(duck.check_flight_conditions())  # Concrete method
print(duck.fly())                      # Implemented abstract method

# Swimmable methods
print(duck.check_water_conditions())   # Concrete method
print(duck.swim())                     # Implemented abstract method

print("\n" + "="*50 + "\n")

# =============================================================================
# 4. ABSTRACT CLASS WITH TEMPLATE METHOD PATTERN
# =============================================================================

class DataProcessor(ABC):
    """
    Abstract class implementing Template Method pattern
    Similar to Java abstract class with template method
    """
    
    def process_data(self, data: List[str]) -> str:
        """
        Template method - defines the algorithm structure
        Concrete method that uses abstract methods
        
        Java equivalent:
        public final String processData(List<String> data) {
            // Same structure
        }
        """
        # Step 1: Validate
        if not self.validate_data(data):
            return "Data validation failed"
        
        # Step 2: Transform
        transformed = self.transform_data(data)
        
        # Step 3: Save
        result = self.save_data(transformed)
        
        return f"Processing complete: {result}"
    
    @abstractmethod
    def validate_data(self, data: List[str]) -> bool:
        """Abstract method - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def transform_data(self, data: List[str]) -> List[str]:
        """Abstract method - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def save_data(self, data: List[str]) -> str:
        """Abstract method - must be implemented by subclasses"""
        pass

class CSVProcessor(DataProcessor):
    """Concrete implementation for CSV processing"""
    
    def validate_data(self, data: List[str]) -> bool:
        """Check if data looks like CSV"""
        return all(',' in line for line in data)
    
    def transform_data(self, data: List[str]) -> List[str]:
        """Transform CSV data"""
        return [line.upper() for line in data]
    
    def save_data(self, data: List[str]) -> str:
        """Save to CSV file"""
        return f"Saved {len(data)} CSV records to file"

class JSONProcessor(DataProcessor):
    """Concrete implementation for JSON processing"""
    
    def validate_data(self, data: List[str]) -> bool:
        """Check if data looks like JSON"""
        return all(line.strip().startswith('{') for line in data)
    
    def transform_data(self, data: List[str]) -> List[str]:
        """Transform JSON data"""
        return [line.replace('{', '{\n  ') for line in data]
    
    def save_data(self, data: List[str]) -> str:
        """Save to JSON file"""
        return f"Saved {len(data)} JSON records to database"

# Usage
csv_data = ["name,age,city", "John,25,NYC", "Jane,30,LA"]
json_data = ['{"name":"John","age":25}', '{"name":"Jane","age":30}']

csv_processor = CSVProcessor()
json_processor = JSONProcessor()

print("CSV Processing:")
print(csv_processor.process_data(csv_data))

print("\nJSON Processing:")
print(json_processor.process_data(json_data))

print("\n" + "="*50 + "\n")

# =============================================================================
# 5. CHECKING ABSTRACT IMPLEMENTATION
# =============================================================================

def demonstrate_abstract_checking():
    """Show how Python handles abstract class instantiation"""
    
    # This will work - all abstract methods implemented
    dog = Dog("Rex", "German Shepherd")
    print(f"Created dog: {dog.name}")
    
    # This would fail - trying to instantiate abstract class
    try:
        animal = Animal("Generic", "Unknown") # type: ignore
    except TypeError as e:
        print(f"Cannot instantiate abstract class: {e}")
    
    # This would fail - incomplete implementation
    class IncompleteBird(Animal):
        def make_sound(self) -> str:
            return "Tweet"

        def move(self) -> str:
            raise NotImplementedError

        # Missing move() method implementation
    
    try:
        incomplete = IncompleteBird("Incomplete", "Bird")
    except TypeError as e:
        print(f"Cannot instantiate incomplete class: {e}")

demonstrate_abstract_checking()

print("\n" + "="*50 + "\n")

# =============================================================================
# 6. MIXIN PATTERN WITH ABSTRACT CLASSES
# =============================================================================

class Debuggable(ABC):
    """
    Abstract mixin class for debugging functionality
    Similar to Java interface but with concrete methods
    """
    
    @abstractmethod
    def get_debug_info(self) -> str:
        """Abstract method for getting debug information"""
        pass
    
    def debug_log(self, message: str) -> None:
        """Concrete method available to all debuggable objects"""
        debug_info = self.get_debug_info()
        print(f"[DEBUG] {debug_info}: {message}")

class Car(Debuggable):
    """Class that uses the debugging mixin"""
    
    def __init__(self, brand: str, model: str):
        self.brand = brand
        self.model = model
        self.speed = 0
    
    def get_debug_info(self) -> str:
        """Implement abstract method"""
        return f"{self.brand} {self.model} (Speed: {self.speed})"
    
    def accelerate(self, amount: int) -> None:
        """Car method that uses debugging"""
        self.speed += amount
        self.debug_log(f"Accelerated by {amount}")

# Usage
car = Car("Toyota", "Camry")
car.accelerate(30)
car.accelerate(20)

print("\n" + "="*50 + "\n")

# =============================================================================
# 7. COMPARISON WITH JAVA
# =============================================================================

# """
# KEY DIFFERENCES FROM JAVA:

# 1. ABSTRACT CLASS DECLARATION:
#    - Python: class MyClass(ABC):
#    - Java: abstract class MyClass
#    - Python: Must import ABC from abc module
#    - Java: abstract keyword is built-in

# 2. ABSTRACT METHODS:
#    - Python: @abstractmethod decorator
#    - Java: abstract keyword before method
#    - Python: Can have implementation (will be overridden)
#    - Java: Cannot have implementation

# 3. ABSTRACT PROPERTIES:
#    - Python: @property + @abstractmethod
#    - Java: Abstract getter/setter methods
#    - Python: More elegant property syntax
#    - Java: More verbose but clearer

# 4. MULTIPLE INHERITANCE:
#    - Python: class Child(Parent1, Parent2, Parent3)
#    - Java: class Child extends Parent implements Interface1, Interface2
#    - Python: Multiple abstract classes allowed
#    - Java: Single inheritance + multiple interfaces

# 5. INSTANTIATION CHECKING:
#    - Python: Runtime TypeError when instantiating abstract class
#    - Java: Compile-time error
#    - Python: More flexible but less safe
#    - Java: Safer but less flexible

# 6. INTERFACE vs ABSTRACT CLASS:
#    - Python: ABC can have concrete methods (like Java 8+ interfaces)
#    - Java: Clear distinction between abstract classes and interfaces
#    - Python: ABC serves both purposes
#    - Java: Two separate concepts

# ADVANTAGES OF PYTHON APPROACH:
# - Less boilerplate code
# - Multiple inheritance support
# - Abstract properties with @property
# - Mixins for cross-cutting concerns
# - Can have concrete methods in abstract classes

# ADVANTAGES OF JAVA APPROACH:
# - Compile-time checking
# - Clearer separation of concerns
# - Better IDE support
# - More predictable behavior
# - Explicit interface contracts

# WHEN TO USE ABSTRACT CLASSES IN PYTHON:
# - When you want to enforce a contract (like Java interfaces)
# - When you have common functionality to share
# - When you want to use the Template Method pattern
# - When you need to define abstract properties
# - When you want to create mixins for cross-cutting concerns
# """