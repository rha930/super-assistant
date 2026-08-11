-- Sample local SQLite database for the agent's database_query connector.
-- Seeded once by the `sqlite-init` service in docker-compose.yml.

CREATE TABLE IF NOT EXISTS places (
    id           INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    city         TEXT    NOT NULL,
    country      TEXT    NOT NULL,
    postal_code  TEXT,
    latitude     REAL    NOT NULL,
    longitude    REAL    NOT NULL
);

INSERT INTO places (id, name, city, country, postal_code, latitude, longitude) VALUES
    (1,  'Eiffel Tower',          'Paris',          'France',         '75007',     48.858370,   2.294481),
    (2,  'Statue of Liberty',     'New York',       'USA',            '10004',     40.689247, -74.044502),
    (3,  'Colosseum',             'Rome',           'Italy',          '00184',     41.890210,  12.492231),
    (4,  'Sydney Opera House',    'Sydney',         'Australia',      '2000',     -33.856784, 151.215297),
    (5,  'Christ the Redeemer',   'Rio de Janeiro', 'Brazil',         '22241-330',-22.951916, -43.210487),
    (6,  'Table Mountain',        'Cape Town',      'South Africa',   '8001',     -33.962700,  18.409600),
    (7,  'Tokyo Tower',           'Tokyo',          'Japan',          '105-0011',  35.658581, 139.745438),
    (8,  'Taj Mahal',             'Agra',           'India',          '282001',    27.175144,  78.042142),
    (9,  'Great Pyramid of Giza', 'Giza',           'Egypt',          '12556',     29.979235,  31.134202),
    (10, 'Machu Picchu',          'Cusco',          'Peru',           '08680',    -13.163141, -72.544963),
    (11, 'Petra',                 'Ma''an',         'Jordan',         '71811',     30.328460,  35.444362),
    (12, 'Big Ben',               'London',         'United Kingdom', 'SW1A 0AA',  51.500729,  -0.124625),
    (13, 'Sagrada Familia',       'Barcelona',      'Spain',          '08013',     41.403629,   2.174356),
    (14, 'Brandenburg Gate',      'Berlin',         'Germany',        '10117',     52.516275,  13.377704),
    (15, 'Burj Khalifa',          'Dubai',          'UAE',            '00000',     25.197197,  55.274376),
    (16, 'Golden Gate Bridge',    'San Francisco',  'USA',            '94129',     37.819929, -122.478255),
    (17, 'CN Tower',              'Toronto',        'Canada',         'M5V 2T6',   43.642566,  -79.387057),
    (18, 'Marina Bay Sands',      'Singapore',      'Singapore',      '018956',     1.283966, 103.860527),
    (19, 'Red Square',            'Moscow',         'Russia',         '109012',    55.753930,  37.620795),
    (20, 'Chichen Itza',          'Tinum',          'Mexico',         '97751',     20.684285,  -88.567783);

