# Advanced E-commerce Backend

A production-ready Django backend for variant-based e-commerce with advanced pricing, inventory, and promotion features.

## Features

- **Variant-based catalog** (colors/sizes) with attributes
- **Inventory management** with inbound shipments and reservations
- **Dynamic pricing engine** with campaigns and price books
- **Time-based promotions** with scheduling and overlap rules
- **Concurrency-safe checkout** with inventory reservation
- **Audit trail** for all price and inventory changes
- **Deterministic price calculation** "as of" any timestamp

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### Setup

1. Clone and install:
```bash
git clone <repository>
cd ecommerce_backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt