from dotenv import load_dotenv
import os
import psycopg2
from psycopg2 import OperationalError

# FastAPI with built-in features
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
from datetime import date


load_dotenv()

# Global connection variable
db_connection = None

# Rate limiting (Python)
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_connection

    db_name = os.getenv("Postgres_db")
    db_user = os.getenv("Postgres_user") or "acro0"
    db_password = os.getenv("Postgres_passwd")
    db_host = 'localhost'
    db_port = int(os.getenv("Postgres_port") or 5432)

    try:
        # Create sync PostgreSQL connection
        # db_connection = psycopg2.connect(
        #     dbname=db_name,
        #     user=db_user,
        #     password=db_password,
        #     host=db_host,
        #     port=db_port
        # )
        db_connection = await asyncpg.create_pool(
            database=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            min_size=5,
            max_size=20
        )

        print("Connection to PostgreSQL  established successfully")
        
        # Yield control back to FastAPI (this is the key fix)
        yield
        
    except OperationalError as e:
        print(f"The error '{e}' occurred")
        yield
    finally:
        # Cleanup connections
        if db_connection:
            await db_connection.close()


app = FastAPI(lifespan=lifespan)

# Add CORS middleware if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# def execute_read_query(connection, query, params=None):
#     """Synchronous function to execute read queries"""
#     cursor = connection.cursor()
#     try:
#         cursor.execute(query, params)
#         rows = cursor.fetchall()
#         print(f"Read Query executed successfully, {cursor.rowcount} rows fetched")
#         return rows
#     except Exception as e:
#         print(f"The error '{e}' occurred")
#         return None
#     finally:
#         cursor.close()


async def execute_read_query(query: str, params=None):
    """Async function to execute read queries"""
    if db_connection is None:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    async with db_connection.acquire() as connection:
        try:
            rows = await connection.fetch(query, *(params or []))
            print(f"Read Query executed successfully, {len(rows)} rows fetched")
            return [dict(row) for row in rows]  # Convert to dict for JSON serialization
        except Exception as e:
            print(f"The error '{e}' occurred")
            raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")
        

# Caching (Python + in-memory)
cached_queries = {}

async def get_cached_data(query: str):
    """Simple async cache implementation"""
    if query in cached_queries:
        print("Cache hit!")
        return cached_queries[query]
    
    data = await execute_read_query(query)
    cached_queries[query] = data
    return data

# Clear cache helper function
def clear_cache():
    """Clear the cache when data is updated"""
    global cached_queries
    cached_queries.clear()
    print("Cache cleared")


# Pagination (Python)
@app.get("/user_data")
async def get_user_data(
    skip: int = 0, 
    limit: int = 20,
):
    read_sql = """
    SELECT * FROM public.Employees;
    """
    
    # Execute query (this will be cached)
    db_data = await get_cached_data(read_sql)
    
    if db_data is None:
        return {"error": "Database connection not available or query failed"}
    
    # Apply pagination
    paginated_data = db_data[skip:skip+limit]
    
    return {
        "data": paginated_data,
        "total": len(db_data),
        "skip": skip,
        "limit": limit,
        "returned": len(paginated_data)
    }

async def execute_update_query(query: str, params=None):
    """Async function to execute update queries"""
    if db_connection is None:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    async with db_connection.acquire() as connection:
        try:
            # For UPDATE/INSERT/DELETE, use execute() not fetch()
            result = await connection.execute(query, *(params or []))
            print(f"Update Query executed successfully, {result} affected")
            return result  # Returns number of affected rows as string like "UPDATE 1"
        except Exception as e:
            print(f"The error '{e}' occurred")
            raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@app.put("/user_data_update/{user_email}")
async def put_user_data(
    user_email: str = Path(..., description="User email to update"),
    limit: int = 20,
):
    try:
        # Fixed: Proper SQL syntax with parameterized query
        update_query = "UPDATE public.employees SET hire_date = $1 WHERE email = $2;"
        params = [date.today(), user_email]
        
        # Execute update query
        result = await execute_update_query(update_query, params)
        
        # Clear cache since data was modified
        clear_cache()
        
        if result is None:
            return {"error": "Database connection not available or query failed"}
        
        # Parse the result to get affected rows count
        affected_rows = int(result.split()[-1]) if result and result.split() else 0
        
        return {
            "message": "User data updated successfully",
            "affected_rows": affected_rows,
            "user_email": user_email,
            "new_hire_date": date.today().isoformat(),
            "limit": limit,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update operation failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "database": "connected" if db_connection else "disconnected"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Testing ...")
    uvicorn.run(
        "Test_PostgreSQL:app",  # This fixes the reload warning
        host="127.0.0.1",
        port=8000,
        reload=True
    )