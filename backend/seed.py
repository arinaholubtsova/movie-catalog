"""Idempotent demo catalog; set ADMIN_EMAIL and ADMIN_PASSWORD to create an admin."""
import os

from sqlalchemy import func, select

from app.auth import hash_password
from app.database import SessionLocal
from app.models import Actor, Director, Genre, Movie, Rating, User
from app.schemas import GENRE_NAMES


DEMO = [
    ("Interstellar", 2014, "Sci-Fi", "space, time, family", 8.6),
    ("Arrival", 2016, "Sci-Fi", "language, aliens, time", 7.9),
    ("The Martian", 2015, "Sci-Fi", "space, survival, mars", 8.0),
    ("Inception", 2010, "Thriller", "dreams, mind, heist", 8.8),
    ("Knives Out", 2019, "Mystery", "detective, family, crime", 7.9),
    ("The Grand Budapest Hotel", 2014, "Comedy", "hotel, friendship, adventure", 8.1),
    ("La La Land", 2016, "Drama", "music, romance, dreams", 8.0),
    ("Whiplash", 2014, "Drama", "music, ambition, mentor", 8.5),
    ("The Dark Knight", 2008, "Action", "hero, crime, city", 9.0),
    ("Spider-Man Into the Spider-Verse", 2018, "Action", "hero, family, animation", 8.4),
    ("Parasite", 2019, "Thriller", "family, class, suspense", 8.5),
    ("The Imitation Game", 2014, "Drama", "history, code, war", 8.0),
    ("Dune: Part Two", 2024, "Sci-Fi", "desert, prophecy, empire", 8.5),
    ("Oppenheimer", 2023, "Drama", "science, history, biography", 8.1),
    ("Everything Everywhere All at Once", 2022, "Sci-Fi", "multiverse, family, identity", 7.8),
    ("The Shawshank Redemption", 1994, "Drama", "prison, hope, friendship", 9.3),
    ("Forrest Gump", 1994, "Drama", "life, love, history", 8.8),
    ("Pulp Fiction", 1994, "Crime", "crime, stories, los angeles", 8.9),
    ("The Lord of the Rings: The Fellowship of the Ring", 2001, "Fantasy", "quest, friendship, middle earth", 8.9),
    ("Spirited Away", 2001, "Animation", "spirits, childhood, courage", 8.6),
    ("Coco", 2017, "Animation", "music, family, memory", 8.4),
    ("The Silence of the Lambs", 1991, "Thriller", "investigation, psychology, crime", 8.6),
    ("Get Out", 2017, "Horror", "mystery, social thriller, family", 7.8),
    ("Mad Max: Fury Road", 2015, "Action", "desert, survival, chase", 8.1),
    ("The Matrix", 1999, "Sci-Fi", "simulation, reality, rebellion", 8.7),
    ("Amélie", 2001, "Romance", "paris, love, kindness", 8.3),
    ("The Truman Show", 1998, "Comedy", "television, reality, freedom", 8.2),
    ("Demo Orbit", 2024, "Sci-Fi", "space, discovery, crew", 7.4),
    ("Demo Harbor", 2023, "Drama", "family, harbor, reunion", 7.1),
    ("Demo Cipher", 2025, "Mystery", "mystery, code, detective", 7.8),
]

POSTERS = {
    "Interstellar": "/posters/interstellar.jpg",
    "Arrival": "/posters/arrival.jpg",
    "The Martian": "/posters/the-martian.jpg",
    "Inception": "/posters/inception.jpg",
    "Knives Out": "/posters/knives-out.jpg",
    "The Grand Budapest Hotel": "/posters/grand-budapest-hotel.jpg",
    "La La Land": "/posters/la-la-land.jpg",
    "Whiplash": "/posters/whiplash.jpg",
    "The Dark Knight": "/posters/the-dark-knight.jpg",
    "Spider-Man Into the Spider-Verse": "/posters/spider-verse.jpg",
    "Parasite": "/posters/parasite.jpg",
    "The Imitation Game": "/posters/the-imitation-game.jpg",
    "Dune: Part Two": "/posters/dune-part-two.jpg",
    "Oppenheimer": "/posters/oppenheimer.jpg",
    "Everything Everywhere All at Once": "/posters/everything-everywhere.jpg",
    "The Shawshank Redemption": "/posters/shawshank-redemption.jpg",
    "Forrest Gump": "/posters/forrest-gump.jpg",
    "Pulp Fiction": "/posters/pulp-fiction.jpg",
    "The Lord of the Rings: The Fellowship of the Ring": "/posters/fellowship-of-the-ring.jpg",
    "Spirited Away": "/posters/spirited-away.jpg",
    "Coco": "/posters/coco.jpg",
    "The Silence of the Lambs": "/posters/silence-of-the-lambs.jpg",
    "Get Out": "/posters/get-out.jpg",
    "Mad Max: Fury Road": "/posters/mad-max-fury-road.jpg",
    "The Matrix": "/posters/the-matrix.jpg",
    "Amélie": "/posters/amelie.jpg",
    "The Truman Show": "/posters/truman-show.jpg",
    "Demo Orbit": "/posters/demo-orbit.svg",
    "Demo Harbor": "/posters/demo-harbor.svg",
    "Demo Cipher": "/posters/demo-cipher.svg",
}

OVERVIEWS = {
    "Interstellar": "Колишній пілот Купер приєднується до космічної експедиції крізь червоточину, щоб знайти новий дім для людства й урятувати майбутнє своїх дітей.",
    "Arrival": "Лінгвістка Луїза Бенкс намагається встановити контакт із прибульцями та зрозуміти їхню мову, яка змінює сприйняття часу.",
    "The Martian": "Астронавт Марк Вотні залишається сам на Марсі й використовує знання та винахідливість, щоб вижити до прибуття рятувальної місії.",
    "Inception": "Дом Кобб проникає у сни людей, але найскладніше завдання вимагає не викрасти ідею, а непомітно закласти її у свідомість.",
    "Knives Out": "Детектив Бенуа Блан розслідує загадкову смерть письменника, підозрюючи кожного члена його великої та суперечливої родини.",
    "The Grand Budapest Hotel": "Консьєрж Ґюстав і його юний помічник Зеро опиняються в центрі пригоди зі спадщиною, картиною та несправедливим звинуваченням.",
    "La La Land": "Джазовий музикант і молода акторка закохуються в Лос-Анджелесі, намагаючись поєднати стосунки з великими творчими мріями.",
    "Whiplash": "Молодий барабанщик потрапляє до оркестру безжального викладача, який випробовує межі його таланту, витривалості й амбіцій.",
    "The Dark Knight": "Бетмен протистоїть Джокеру, який занурює Ґотем у хаос і змушує його перевірити власні моральні принципи.",
    "Spider-Man Into the Spider-Verse": "Підліток Майлз Моралес отримує здібності Людини-павука й зустрічає героїв з інших вимірів, щоб разом урятувати мультивсесвіт.",
    "Parasite": "Родина Кімів поступово влаштовується на роботу до заможної сім’ї Паків, але їхній план набуває несподіваного й небезпечного розвитку.",
    "The Imitation Game": "Математик Алан Тюрінг очолює команду, яка намагається зламати шифр Enigma під час Другої світової війни.",
    "Dune: Part Two": "Пол Атрейдес об’єднується з фременами, щоб помститися змовникам і спробувати відвернути війну, яку бачить у своїх видіннях.",
    "Oppenheimer": "Історія фізика Роберта Оппенгеймера та створення атомної бомби, що назавжди змінила світ.",
    "Everything Everywhere All at Once": "Власниця пральні потрапляє у вир паралельних світів і мусить урятувати родину та весь мультивсесвіт.",
    "The Shawshank Redemption": "Банкір, несправедливо засуджений до довічного ув’язнення, знаходить дружбу й надію за стінами Шоушенка.",
    "Forrest Gump": "Добросердий Форрест несподівано опиняється в центрі ключових подій американської історії, не забуваючи про своє кохання.",
    "Pulp Fiction": "Кілька кримінальних історій Лос-Анджелеса переплітаються у дотепну й непередбачувану мозаїку.",
    "The Lord of the Rings: The Fellowship of the Ring": "Фродо вирушає в небезпечну подорож, щоб знищити Перстень і зупинити повернення Темного Володаря.",
    "Spirited Away": "Дівчинка Тіхіро потрапляє у світ духів і вчиться бути сміливою, щоб урятувати своїх батьків.",
    "Coco": "Юний Міґель опиняється у Країні Мертвих, де відкриває таємницю своєї родини й силу пам’яті.",
    "The Silence of the Lambs": "Молода агентка ФБР звертається по допомогу до блискучого ув’язненого психіатра, щоб спіймати серійного вбивцю.",
    "Get Out": "Знайомство з родиною дівчини перетворюється для Кріса на тривожну пастку з моторошною таємницею.",
    "Mad Max: Fury Road": "У спустошеному світі Макс і Фуріоза тікають від тирана через пустелю в шаленій гонитві за свободою.",
    "The Matrix": "Хакер Нео дізнається, що звичний світ є симуляцією, і приєднується до боротьби за людство.",
    "Amélie": "Мрійлива парижанка таємно змінює життя людей навколо, поки не наважується подбати про власне щастя.",
    "The Truman Show": "Трумен поступово розуміє, що все його життя є телевізійним шоу, а навколишній світ — великою декорацією.",
    "Demo Orbit": "Екіпаж дослідницького корабля вирушає до невідомої планети й знаходить сигнал, що може змінити уявлення людства про космос.",
    "Demo Harbor": "Після багатьох років розлуки родина збирається в маленькому портовому місті, щоб примиритися з минулим і почати нове життя.",
    "Demo Cipher": "Детективка розшифровує серію загадкових повідомлень, які ведуть до давньої справи та небезпечної таємниці міста.",
}

PEOPLE = {
    "Interstellar": (["Matthew McConaughey", "Anne Hathaway", "Jessica Chastain"], ["Christopher Nolan"]),
    "Arrival": (["Amy Adams", "Jeremy Renner", "Forest Whitaker"], ["Denis Villeneuve"]),
    "The Martian": (["Matt Damon", "Jessica Chastain", "Kristen Wiig"], ["Ridley Scott"]),
    "Inception": (["Leonardo DiCaprio", "Joseph Gordon-Levitt", "Elliot Page"], ["Christopher Nolan"]),
    "Knives Out": (["Daniel Craig", "Chris Evans", "Ana de Armas"], ["Rian Johnson"]),
    "The Grand Budapest Hotel": (["Ralph Fiennes", "Tony Revolori", "Saoirse Ronan"], ["Wes Anderson"]),
    "La La Land": (["Ryan Gosling", "Emma Stone", "John Legend"], ["Damien Chazelle"]),
    "Whiplash": (["Miles Teller", "J.K. Simmons", "Paul Reiser"], ["Damien Chazelle"]),
    "The Dark Knight": (["Christian Bale", "Heath Ledger", "Aaron Eckhart"], ["Christopher Nolan"]),
    "Spider-Man Into the Spider-Verse": (["Shameik Moore", "Jake Johnson", "Hailee Steinfeld"], ["Bob Persichetti", "Peter Ramsey", "Rodney Rothman"]),
    "Parasite": (["Song Kang-ho", "Lee Sun-kyun", "Cho Yeo-jeong"], ["Bong Joon Ho"]),
    "The Imitation Game": (["Benedict Cumberbatch", "Keira Knightley", "Matthew Goode"], ["Morten Tyldum"]),
    "Dune: Part Two": (["Timothée Chalamet", "Zendaya", "Rebecca Ferguson"], ["Denis Villeneuve"]),
    "Oppenheimer": (["Cillian Murphy", "Emily Blunt", "Matt Damon"], ["Christopher Nolan"]),
    "Everything Everywhere All at Once": (["Michelle Yeoh", "Ke Huy Quan", "Stephanie Hsu"], ["Daniel Kwan", "Daniel Scheinert"]),
    "The Shawshank Redemption": (["Tim Robbins", "Morgan Freeman", "Bob Gunton"], ["Frank Darabont"]),
    "Forrest Gump": (["Tom Hanks", "Robin Wright", "Gary Sinise"], ["Robert Zemeckis"]),
    "Pulp Fiction": (["John Travolta", "Samuel L. Jackson", "Uma Thurman"], ["Quentin Tarantino"]),
    "The Lord of the Rings: The Fellowship of the Ring": (["Elijah Wood", "Ian McKellen", "Viggo Mortensen"], ["Peter Jackson"]),
    "Spirited Away": (["Rumi Hiiragi", "Miyu Irino", "Mari Natsuki"], ["Hayao Miyazaki"]),
    "Coco": (["Anthony Gonzalez", "Gael García Bernal", "Benjamin Bratt"], ["Lee Unkrich"]),
    "The Silence of the Lambs": (["Jodie Foster", "Anthony Hopkins", "Scott Glenn"], ["Jonathan Demme"]),
    "Get Out": (["Daniel Kaluuya", "Allison Williams", "Bradley Whitford"], ["Jordan Peele"]),
    "Mad Max: Fury Road": (["Tom Hardy", "Charlize Theron", "Nicholas Hoult"], ["George Miller"]),
    "The Matrix": (["Keanu Reeves", "Laurence Fishburne", "Carrie-Anne Moss"], ["Lana Wachowski", "Lilly Wachowski"]),
    "Amélie": (["Audrey Tautou", "Mathieu Kassovitz", "Rufus"], ["Jean-Pierre Jeunet"]),
    "The Truman Show": (["Jim Carrey", "Laura Linney", "Ed Harris"], ["Peter Weir"]),
    "Demo Orbit": (["Maya Brooks", "Ethan Cole", "Noah Reed"], ["Lena Hart"]),
    "Demo Harbor": (["Olivia Stone", "Daniel Ross", "Sophie Lane"], ["Martin Wells"]),
    "Demo Cipher": (["Nina Blake", "Marcus Reed", "Eva Stone"], ["Adrian Cross"]),
}

EXTERNAL_IDS = {
    "Demo Orbit": "demo-orbit-2024",
    "Demo Harbor": "demo-harbor-2023",
    "Demo Cipher": "demo-cipher-2025",
}

def named_people(db, model, values):
    people = []
    for name in values:
        person = db.scalar(select(model).where(model.name == name))
        if person is None:
            person = model(name=name)
            db.add(person)
            db.flush()
        people.append(person)
    return people


def seed():
    with SessionLocal() as db:
        catalog = {}
        for genre_name in GENRE_NAMES:
            genre = db.scalar(select(Genre).where(Genre.name == genre_name))
            if genre is None:
                genre = Genre(name=genre_name)
                db.add(genre)
                db.flush()
            catalog[genre_name] = genre
        for title, year, genre_name, keywords, avg_rating in DEMO:
            movie = db.scalar(select(Movie).where(Movie.title == title, Movie.year == year))
            if movie is None:
                movie = Movie(title=title, year=year)
                db.add(movie)
            movie.overview = OVERVIEWS[title]
            movie.keywords = keywords
            movie.poster_url = POSTERS[title]
            movie.base_rating = avg_rating
            movie.base_rating_count = 100
            movie.genres = [catalog[genre_name]]
            movie.external_id = EXTERNAL_IDS.get(title, movie.external_id)
            actor_names, director_names = PEOPLE[title]
            movie.actors = named_people(db, Actor, actor_names)
            movie.directors = named_people(db, Director, director_names)
            user_average, user_count = (None, 0) if movie.id is None else db.execute(
                select(func.avg(Rating.value), func.count(Rating.value)).where(Rating.movie_id == movie.id)
            ).one()
            user_count = int(user_count or 0)
            movie.rating_count = movie.base_rating_count + user_count
            movie.avg_rating = (
                movie.base_rating * movie.base_rating_count + 2 * float(user_average or 0) * user_count
            ) / movie.rating_count
        email, password = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
        if email and password and db.scalar(select(User).where(User.email == email.lower())) is None:
            if len(password) < 8:
                raise ValueError("ADMIN_PASSWORD must have at least 8 characters")
            db.add(User(email=email.lower(), password_hash=hash_password(password), role="admin"))
        db.commit()


if __name__ == "__main__":
    seed()
