from sqlalchemy import Column, ForeignKey, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    picture = Column(String(250))


class Genre(Base):
    __tablename__ = 'genre'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False, unique=True)


class Tvshow(Base):
    __tablename__ = 'tvshow'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    cover_url = Column(String(250))
    release_date = Column(Date)
    imdb_id = Column(String(50), nullable=False, unique=True)

    # Relationships
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user = relationship(User)

    # If the Tvshow should be deleted, so will the episodes.
    episodes = relationship("Episode", back_populates='tvshow',
                            cascade='all, delete, delete-orphan')
    # Lets me go from an individual Tvshow to the Genre object through GenreShow
    genreshow = relationship("GenreShow", back_populates='tvshow',
                             cascade='all, delete, delete-orphan')
    genres = relationship('GenreShow')

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'id': self.id,
            'name': self.name,
            'imdb_id': self.imdb_id,
            'user_id': self.user_id,
        }


class GenreShow(Base):
    __tablename__ = 'genre_show'

    id = Column(Integer, primary_key=True)

    genre_id = Column(Integer, ForeignKey('genre.id'))
    tvshow_id = Column(Integer, ForeignKey('tvshow.id'))
    tvshow = relationship('Tvshow', back_populates='genreshow')

    genre = relationship(Genre)


class Episode(Base):
    __tablename__ = 'episode'

    title = Column(String(80))
    id = Column(Integer, primary_key=True)
    airdate = Column(Date)
    season = Column(Integer)
    episode_num = Column(Integer)
    episode_imdb_id = Column(String(50), unique=True)

    tvshow_id = Column(Integer, ForeignKey('tvshow.id'))
    tvshow = relationship('Tvshow', back_populates='episodes')

    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user = relationship(User)

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'id': self.id,
            'title': self.title,
            'airdate': str(self.airdate),
            'season': self.season,
            'episode_num': self.episode_num,
        }


engine = create_engine('sqlite:///fomo.db')

Base.metadata.create_all(engine)
