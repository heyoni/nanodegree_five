from sqlalchemy import create_engine
from sqlalchemy import exc
from sqlalchemy.orm import sessionmaker
import imdbpie
import datetime
from database_setup import User, Tvshow, Season, Episode, Genre, Base, GenreShow
import pickle

engine = create_engine('sqlite:///fomo.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

imdb = imdbpie.Imdb()

IMDB_ID = ['tt0944947', 'tt2861424', 'tt0475784', 'tt0903747', 'tt1856010',
           'tt0386676', 'tt4158110', 'tt0472954', 'tt1266020', 'tt2467372', ]

def fetch_from_imdb(imdb_list):
    series = []
    episodes = []
    for id in imdb_list:
        series.append(imdb.get_title_by_id(id))
        episodes.append(imdb.get_episodes(series[-1].imdb_id))
    return series, episodes

def pickle_imdb(series, episodes):
    # accepts a list of imdb objects
    pickle.dump(series, open('series.pickle', 'w+'))
    pickle.dump(episodes, open('episodes.pickle', 'w+'))

def populate(episodes, imdb_show):

    # Form the release date
    try:
        year, month, day = int(imdb_show.release_date.split('-')[0]), \
                           int(imdb_show.release_date.split('-')[1]), \
                           int(imdb_show.release_date.split('-')[2])
        release_date = datetime.date(year, month, day)
    except AttributeError:
        year, month, day = imdb_show.year, 1, 1
        release_date = datetime.date(year, month, day)
    # Add the TVShow
    tvshow = Tvshow(name=imdb_show.title, cover_url=imdb_show.cover_url,
                       release_date=release_date, imdb_id=imdb_show.imdb_id,
                       user_id=1)
    session.add(tvshow)
    try:
        session.commit()
    except exc.IntegrityError:
        session.rollback()
        print('tvshow %s already in db' % imdb_show.title)
        del tvshow
    # Add any new genres that this show contains
    for genre in imdb_show.genres:
        newGenre = Genre(name=genre)
        session.add(newGenre)
        try:
            session.commit()
        except exc.IntegrityError:
            print('%s already exist in genre table' % genre)
            session.rollback()
            newGenre = session.query(Genre).filter_by(name=genre).one()
        # Pair up Genre with Tvshow
        session.add(GenreShow(genre_id=newGenre.id, tvshow_id=tvshow.id))
    parent = session.query(Tvshow).filter_by(imdb_id=imdb_show.imdb_id).one()

    def add_date(index):
        try:
            return int(episode.release_date.split('-')[index])
        except (AttributeError, IndexError):
            return 0

    for episode in episodes:
        year = add_date(0)
        month = add_date(1)
        day = add_date(2)

        try:
            release_date = datetime.date(year, month, day)
        except ValueError:
            release_date = None
        session.add(Episode(title=episode.title, season=episode.season,
                            tvshow_id=parent.id,
                            episode_imdb_id=episode.imdb_id,
                            episode_num=episode.episode, airdate=release_date,
                            user_id=1))
    try:
        session.commit()
    except exc.IntegrityError:
        session.rollback()
        print('episode already exists')


# series, episodes = fetch_from_imdb(IMDB_ID)
# pickle_imdb(series, episodes)

with open('series.pickle', 'r') as F, open('episodes.pickle', 'r') as G:
    tvshows = pickle.load(F)
    episodes = pickle.load(G)
    for show in zip(tvshows, episodes):
        populate(episodes=show[1], imdb_show=show[0])