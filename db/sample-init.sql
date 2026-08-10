-- Sample local SQLite database for the agent's database_query connector.
-- Seeded once by the `sqlite-init` service in docker-compose.yml.

CREATE TABLE IF NOT EXISTS customers (
    id       INTEGER PRIMARY KEY,
    name     TEXT    NOT NULL,
    email    TEXT    NOT NULL,
    country  TEXT    NOT NULL,
    created  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(id),
    product      TEXT    NOT NULL,
    amount       REAL    NOT NULL,
    ordered_at   TEXT    NOT NULL
);

INSERT INTO customers (id, name, email, country, created) VALUES
    (1, 'Ada Lovelace',    'ada@example.com',    'UK',      '2026-01-05'),
    (2, 'Alan Turing',     'alan@example.com',   'UK',      '2026-01-11'),
    (3, 'Grace Hopper',    'grace@example.com',  'USA',     '2026-02-02'),
    (4, 'Katherine Johnson','kj@example.com',    'USA',     '2026-02-20'),
    (5, 'Linus Torvalds',  'linus@example.com',  'Finland', '2026-03-15');

INSERT INTO orders (id, customer_id, product, amount, ordered_at) VALUES
    (1, 1, 'Analytical Engine Blueprint', 1200.00, '2026-03-01'),
    (2, 1, 'Punch Card Pack',               45.50, '2026-03-04'),
    (3, 3, 'COBOL Manual',                  30.00, '2026-03-09'),
    (4, 4, 'Orbital Calculator',           250.75, '2026-03-12'),
    (5, 5, 'Kernel Sticker Set',            12.99, '2026-03-18'),
    (6, 2, 'Enigma Replica',               999.99, '2026-03-21');
