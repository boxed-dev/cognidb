-- Seed data for commerce fixture

INSERT INTO categories (id, name, parent_id) VALUES
  (1, 'Electronics', NULL),
  (2, 'Computers', 1),
  (3, 'Phones', 1),
  (4, 'Home', NULL),
  (5, 'Kitchen', 4);

INSERT INTO products (id, sku, name, category_id, unit_price, active, created_at) VALUES
  (1, 'LAP-001', 'Ultrabook 14', 2, 999.00, 1, '2024-01-10'),
  (2, 'LAP-002', 'Workstation 16', 2, 1899.00, 1, '2024-02-15'),
  (3, 'PHN-001', 'Pixel Phone', 3, 699.00, 1, '2024-03-01'),
  (4, 'PHN-002', 'Budget Phone', 3, 199.00, 1, '2023-11-20'),
  (5, 'KIT-001', 'Blender Pro', 5, 89.50, 1, '2024-01-05'),
  (6, 'KIT-002', 'Toaster Mini', 5, 29.99, 0, '2023-08-12'),
  (7, 'HOM-001', 'Desk Lamp', 4, 45.00, 1, '2024-04-01'),
  (8, 'HOM-002', 'Standing Desk', 4, 499.00, 1, '2024-05-10');

INSERT INTO customers (id, name, email, country, city, created_at, is_vip) VALUES
  (1, 'Ada Lovelace', 'ada@example.com', 'UK', 'London', '2023-01-15', 1),
  (2, 'Grace Hopper', 'grace@example.com', 'US', 'New York', '2023-03-22', 1),
  (3, 'Alan Turing', 'alan@example.com', 'UK', 'Manchester', '2023-06-01', 0),
  (4, 'Katherine Johnson', 'kj@example.com', 'US', 'Hampton', '2024-01-08', 0),
  (5, 'Donald Knuth', 'knuth@example.com', 'US', 'Stanford', '2022-12-01', 1),
  (6, 'Barbara Liskov', 'bl@example.com', 'US', 'Boston', '2024-02-14', 0),
  (7, 'Tim Berners-Lee', 'tbl@example.com', 'UK', 'London', '2023-09-30', 0),
  (8, 'Radia Perlman', 'rp@example.com', 'US', 'Redmond', '2024-03-18', 0);

INSERT INTO employees (id, name, role, manager_id, hire_date) VALUES
  (1, 'Sam Manager', 'manager', NULL, '2020-01-01'),
  (2, 'Alex Sales', 'sales', 1, '2021-05-15'),
  (3, 'Jordan Support', 'support', 1, '2022-08-20'),
  (4, 'Riley Sales', 'sales', 1, '2023-02-10');

INSERT INTO orders (id, customer_id, employee_id, status, order_date, ship_date, total_amount) VALUES
  (1, 1, 2, 'shipped', '2024-01-20', '2024-01-22', 1098.00),
  (2, 2, 2, 'shipped', '2024-02-01', '2024-02-03', 699.00),
  (3, 3, 4, 'pending', '2024-03-10', NULL, 89.50),
  (4, 1, 4, 'shipped', '2024-03-15', '2024-03-17', 544.00),
  (5, 4, 2, 'cancelled', '2024-03-18', NULL, 199.00),
  (6, 5, 2, 'shipped', '2024-04-01', '2024-04-02', 1899.00),
  (7, 6, 4, 'pending', '2024-04-12', NULL, 45.00),
  (8, 2, 2, 'shipped', '2024-05-01', '2024-05-03', 728.99),
  (9, 7, 3, 'shipped', '2024-05-20', '2024-05-21', 999.00),
  (10, 8, 4, 'pending', '2024-06-01', NULL, 499.00);

INSERT INTO order_items (id, order_id, product_id, quantity, unit_price) VALUES
  (1, 1, 1, 1, 999.00),
  (2, 1, 5, 1, 89.50),
  (3, 1, 7, 0, 0.00),
  (4, 2, 3, 1, 699.00),
  (5, 3, 5, 1, 89.50),
  (6, 4, 8, 1, 499.00),
  (7, 4, 7, 1, 45.00),
  (8, 5, 4, 1, 199.00),
  (9, 6, 2, 1, 1899.00),
  (10, 7, 7, 1, 45.00),
  (11, 8, 3, 1, 699.00),
  (12, 8, 6, 1, 29.99),
  (13, 9, 1, 1, 999.00),
  (14, 10, 8, 1, 499.00);

INSERT INTO payments (id, order_id, method, amount, paid_at, status) VALUES
  (1, 1, 'card', 1098.00, '2024-01-20', 'captured'),
  (2, 2, 'card', 699.00, '2024-02-01', 'captured'),
  (3, 3, 'paypal', 89.50, NULL, 'pending'),
  (4, 4, 'card', 544.00, '2024-03-15', 'captured'),
  (5, 5, 'card', 199.00, '2024-03-18', 'refunded'),
  (6, 6, 'wire', 1899.00, '2024-04-01', 'captured'),
  (7, 7, 'card', 45.00, NULL, 'pending'),
  (8, 8, 'card', 728.99, '2024-05-01', 'captured'),
  (9, 9, 'card', 999.00, '2024-05-20', 'captured'),
  (10, 10, 'paypal', 499.00, NULL, 'pending');

INSERT INTO reviews (id, product_id, customer_id, rating, body, created_at) VALUES
  (1, 1, 1, 5, 'Excellent laptop', '2024-02-01'),
  (2, 1, 7, 4, 'Solid build', '2024-06-01'),
  (3, 3, 2, 5, 'Great phone', '2024-02-15'),
  (4, 5, 3, 3, 'Average blender', '2024-03-20'),
  (5, 2, 5, 5, 'Powerhouse machine', '2024-04-10'),
  (6, 8, 1, 4, 'Sturdy desk', '2024-03-25'),
  (7, 4, 4, 2, 'Battery drains fast', '2024-04-01'),
  (8, 7, 6, 5, 'Bright and cheap', '2024-04-20');
