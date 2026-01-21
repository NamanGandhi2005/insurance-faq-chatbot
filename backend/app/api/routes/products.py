# app/api/routes/products.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List
from app.database.connection import get_db
from app.models.product import Product
from app.models.user import User
from app.utils.security import get_current_admin
from app.utils.encryption import encrypt_id, decrypt_id

router = APIRouter()

# --- Schemas ---
class ProductCreate(BaseModel):
    name: str
    description: str | None = None

class ProductResponse(BaseModel):
    id: str  # Encrypted ID
    name: str
    description: str | None
    
    class Config:
        from_attributes = True

# --- Routes ---

# 1. CREATE (Protected)
@router.post("/", response_model=ProductResponse)
def create_product(
    product: ProductCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    existing = db.query(Product).filter(Product.name == product.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Product already exists")
    
    new_product = Product(name=product.name, description=product.description)
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    
    return ProductResponse(
        id=encrypt_id(new_product.id),
        name=new_product.name,
        description=new_product.description
    )

# 2. LIST (Public)
@router.get("/", response_model=List[ProductResponse])
def list_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return [
        ProductResponse(
            id=encrypt_id(p.id),
            name=p.name,
            description=p.description
        ) for p in products
    ]

# 3. GET ONE (Public)
@router.get("/{encrypted_product_id}", response_model=ProductResponse)
def get_product(encrypted_product_id: str, db: Session = Depends(get_db)):
    product_id = decrypt_id(encrypted_product_id)
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    return ProductResponse(
        id=encrypt_id(product.id),
        name=product.name,
        description=product.description
    )

# 4. UPDATE (Protected)
@router.put("/{encrypted_product_id}", response_model=ProductResponse)
def update_product(
    encrypted_product_id: str, 
    product_data: ProductCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    product_id = decrypt_id(encrypted_product_id)
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product.name = product_data.name
    product.description = product_data.description
    
    try:
        db.commit()
        db.refresh(product)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error updating product. Name might be duplicate.")
        
    return ProductResponse(
        id=encrypt_id(product.id),
        name=product.name,
        description=product.description
    )

# 5. DELETE (Protected)
@router.delete("/{encrypted_product_id}")
def delete_product(
    encrypted_product_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    product_id = decrypt_id(encrypted_product_id)
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Note: This might fail if there are foreign keys (PDFs, Logs) attached.
    # In a real app, you would cascade delete or check dependencies.
    try:
        db.delete(product)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Cannot delete product. It may have associated PDFs or Logs.")
        
    return {"message": "Product deleted successfully"}