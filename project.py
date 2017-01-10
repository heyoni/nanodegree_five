from flask import Flask, render_template, request, redirect, jsonify, url_for, \
    flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, Tvshow, Episode, Genre, GenreShow
from flask import session as login_session
import random
import string
import datetime
from functools import wraps


# IMPORTS FOR THIS STEP
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "fomo"

# Connect to Database and create database session
engine = create_engine('sqlite:///fomo.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print
        "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'),
            200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['credentials'] = credentials
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    # ADD PROVIDER TO LOGIN SESSION
    login_session['provider'] = 'google'

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print
    "done!"
    return output


@app.route('/gdisconnect')
def gdisconnect():
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(json.dumps('Current user not connected'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = credentials.access_token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    if result['status'] == '200':
        del login_session['gplus_id']

        response = make_response(json.dumps('Successfully disconnected'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response('Failed to revoke token for given user', 400)
        response.headers['Content-Type'] = 'application/json'
        return response


@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data

    # Exchange client token for long-lived server-side token with GET
    # /oauth/access_token?grant_type=fb_exchange_token&client_id={app-id}
    # &client_secret={app-secret}&fb_exchange_token={short-lived-token}
    app_id = json.loads(open('fb_client_secrets.json', 'r').read())['web'][
        'app_id']
    app_secret = json.loads(open('fb_client_secrets.json', 'r').read())['web'][
        'app_secret']
    url = 'https://graph.facebook.com/oauth/access_token?grant_type=' \
          'fb_exchange_token&client_id=%s&client_secret=%s&' \
          'fb_exchange_token=%s' % (app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # use token to get info from API
    userinfo_url = "https://graph.facebook.com/v2.4/me"
    # strip expire tag from access token
    token = result.split("&")[0]

    url = 'https://graph.facebook.com/v2.4/me?%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order to properly logout, let's strip out the information before the equals sign in our token
    stored_token = token.split("=")[1]
    login_session['access_token'] = stored_token

    # Get user picture
    url = 'https://graph.facebook.com/v2.4/me/picture?%s&redirect=0&height=200&width=200' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data["data"]["url"]

    # see if user exists
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '

    flash("Now logged in as %s" % login_session['username'])
    return output

    # data = json.loads()


@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    # The access token must me included to successfully logout
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (
        facebook_id, access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return "you have been logged out"


def createUser(login_session):
    newUser = User(name=login_session['username'],
                   email=login_session['email'],
                   picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# JSON APIs to view Tvshow Information

@app.route('/tvshow/JSON')
def tvShowJSON():
    tvshows = session.query(Tvshow).all()
    return jsonify(tvshow=[r.serialize for r in tvshows])


@app.route('/tvshow/<int:tvshow_id>/episodes/JSON')
def episodesJSON(tvshow_id):
    episodes = session.query(Tvshow).filter_by(id=tvshow_id).one().episodes
    return jsonify(Episodes=[e.serialize for e in episodes])


@app.route('/episode/<int:episode_id>/JSON')
@app.route('/tvshow/<int:tvshow_id>/episodes/<int:episode_id>/JSON')
def episodeJSON(episode_id, tvshow_id):
    episode = session.query(Episode).filter_by(id=episode_id)
    return jsonify(episode.one().serialize)


@app.route('/tvshow/category/<string:category>/JSON')
def menuItemJSON(category):
    genre_id = session.query(Genre).filter_by(name=category).one().id
    genreShowLocal = session.query(GenreShow).filter_by(
        genre_id=genre_id).all()
    tvshows = [genreShow.tvshow for genreShow in genreShowLocal]
    return jsonify(tvshow_by_genre=[e.serialize for e in tvshows])


@app.route('/')
@app.route('/tvshow/')
def showTvshows():
    tvshows = session.query(Tvshow).order_by(asc(Tvshow.name))
    # filter out genres not associated with any existing tvshows
    genres = session.query(Genre).join(GenreShow).filter(
        GenreShow.genre_id == Genre.id)
    if 'username' not in login_session:
        return render_template('publictvshows.html',
                               tvshows=tvshows, genres=genres)
    else:
        return render_template('tvshows.html', tvshows=tvshows, genres=genres)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in login_session:
            return redirect('/login')
        else:
            return f(*args, **kwargs)

    return decorated_function


@app.route('/tvshow/new/', methods=['GET', 'POST'])
@login_required
def newTvshow():
    if request.method == 'POST':
        newTvshow = Tvshow(name=request.form['name'],
                           imdb_id=request.form['imdb_id'],
                           user_id=login_session['user_id'])
        session.add(newTvshow)
        flash('New Tvshow %s Successfully Created' % newTvshow.name)
        session.commit()
        return redirect(url_for('showTvshows'))
    else:
        return render_template('newTvshow.html')


def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        tvShow = session.query(Tvshow).filter_by(id=kwargs['tvshow_id']).one()
        if 'username' not in login_session or tvShow.user.id != \
                login_session[
                    'user_id']:
            return redirect('/login')
        else:
            return f(*args, **kwargs)

    return decorated_function


@app.route('/tvshow/<int:tvshow_id>/edit/', methods=['GET', 'POST'])
@auth_required
def editTvshow(tvshow_id):
    editedTvshow = session.query(Tvshow).filter_by(id=tvshow_id).one()
    # if 'username' not in login_session or editedTvshow.user.id != \
    #         login_session[
    #             'user_id']:
    #     return redirect('/login')
    if request.method == 'POST':
        # If the user changes the movie's title
        if request.form['name']:
            editedTvshow.name = request.form['name']
            flash('Tvshow Successfully Edited %s' % editedTvshow.name)
        # If the user changes any of the genres
        genreShowLocalList = session.query(GenreShow).filter_by(
            tvshow_id=editedTvshow.id).all()
        # delete any unchecked genre box from GenreShow
        for genreShowLocal in genreShowLocalList:
            if not request.form.keys().__contains__(genreShowLocal.genre.name):
                session.delete(genreShowLocal)
        # add any new genre to Genre and to GenreShow
        for k, v in request.form.items():
            if v == 'on':
                # get genre locally first
                try:
                    genreLocal = session.query(Genre).filter_by(name=k).one()
                except NoResultFound:
                    genreLocal = Genre(name=k)
                    session.add(genreLocal)
                    session.commit()
                # with local genre, create a GenreShow relationship
                try:
                    session.query(GenreShow).filter_by(
                        tvshow_id=editedTvshow.id,
                        genre_id=genreLocal.id).one()
                except NoResultFound:
                    try:
                        newGenreShow = GenreShow(tvshow_id=editedTvshow.id,
                                                 genre_id=genreLocal.id)
                        session.add(newGenreShow)
                        session.commit()
                        flash(
                            'Successfully created GenreShow relationship for '
                            '%s: %s' % (
                                genreLocal.name, editedTvshow.name))
                    except:
                        session.flush()
                        flash('failed to create GenreShow relationship')
        return redirect(url_for('showTvshows'))
    else:
        return render_template('editTvshow.html',
                               tvshow=editedTvshow)


@app.route('/tvshow/<int:tvshow_id>/delete/', methods=['GET', 'POST'])
@auth_required
def deleteTvshow(tvshow_id):
    delTvshow = session.query(Tvshow).filter_by(id=tvshow_id).one()
    # if 'username' not in login_session or delTvshow.user.id != login_session[
    #     'user_id']:
    #     return redirect('/login')
    if request.method == 'POST':
        session.delete(delTvshow)
        flash('%s Successfully Deleted' % delTvshow.name)
        session.commit()
        return redirect(url_for('showTvshows', tvshow_id=tvshow_id))
    else:
        return render_template('deleteTvshow.html', tvshow=delTvshow)


@app.route('/tvshow/<int:tvshow_id>/')
@app.route('/tvshow/<int:tvshow_id>/episodes/')
def showEpisodes(tvshow_id):
    tvshow = session.query(Tvshow).filter_by(id=tvshow_id).one()
    episodes = session.query(Episode).filter_by(
        tvshow_id=tvshow_id).all()
    creator = getUserInfo(tvshow.user_id)
    if 'username' not in login_session or creator.id != login_session[
        'user_id']:
        return render_template('publicepisodes.html', episodes=episodes,
                               tvshow=tvshow, creator=creator)
    else:
        return render_template('episodes.html', episodes=episodes,
                               tvshow=tvshow)


@app.route('/tvshow/category/<string:category>/', methods=['GET'])
def displayCategory(category):
    genre_id = session.query(Genre).filter_by(name=category).one().id
    genreshows = session.query(GenreShow).filter_by(genre_id=genre_id).all()
    # making sure we send the right Tvshow obj
    tvshows = []
    genres = session.query(Genre).join(GenreShow).filter(
        GenreShow.genre_id == Genre.id)
    for tvshow in genreshows:
        tvshows.append(tvshow.tvshow)
    # genre = [genreshows[0].genre.name, ]
    return render_template('tvshows.html', tvshows=tvshows, genres=genres)


def airdate_datetime(airdate):
    """

    Convert a string in the form of year-mont-day into a datetime.date object

    Example:
        airdate_datetime('1999-12-31') will return datetime.date(1999, 12,
        31) which can then be properly inserted into the db, which requires
        datetime.date objects.
    """
    year = int(airdate.split('-')[0])
    month = int(airdate.split('-')[1])
    day = int(airdate.split('-')[2])
    return datetime.date(year, month, day)


# Create a new menu item
@app.route('/tvshow/<int:tvshow_id>/episode/new/', methods=['GET', 'POST'])
@auth_required
def newEpisode(tvshow_id):
    tvshow = session.query(Tvshow).filter_by(id=tvshow_id).one()
    if request.method == 'POST':
        airdatetime = airdate_datetime(request.form['airdate'])
        new_episode = Episode(title=request.form['title'], airdate=airdatetime,
                              season=request.form['season'],
                              episode_num=request.form['episode'],
                              tvshow_id=tvshow.id,
                              user_id=login_session['user_id'])
        session.add(new_episode)
        session.commit()
        flash('New Episode %s Item Successfully Created' % new_episode.title)
        return redirect(url_for('showEpisodes', tvshow_id=tvshow_id))
    else:
        return render_template('newepisode.html', tvshow_id=tvshow_id)


@app.route('/tvshow/<int:tvshow_id>/episodes/<int:episode_id>/edit',
           methods=['GET', 'POST'])
@auth_required
def editEpisode(tvshow_id, episode_id):
    editedEpisode = session.query(Episode).filter_by(id=episode_id).one()
    editedShow = session.query(Tvshow).filter_by(id=tvshow_id).one()
    if request.method == 'POST':
        if request.form['title']:
            editedEpisode.title = request.form['title']
        if request.form['season']:
            editedEpisode.season = request.form['season']
        if request.form['episode']:
            editedEpisode.episode_num = request.form['episode']
        if request.form['airdate']:
            year = int(request.form['airdate'].split('-')[0])
            month = int(request.form['airdate'].split('-')[1])
            day = int(request.form['airdate'].split('-')[2])
            airdate = datetime.date(year, month, day)
            editedEpisode.airdate = airdate
        session.add(editedEpisode)
        session.commit()
        flash('%s Successfully Edited' % editedEpisode.title)
        return redirect(url_for('showEpisodes', tvshow_id=tvshow_id))
    else:
        return render_template('editepisode.html', tvshow_id=tvshow_id,
                               episode_id=episode_id, episode=editedEpisode)


# Delete a menu item
@app.route('/tvshow/<int:tvshow_id>/episodes/<int:episode_id>/delete',
           methods=['GET', 'POST'])
@auth_required
def deleteEpisode(tvshow_id, episode_id):
    tvshow = session.query(Tvshow).filter_by(id=tvshow_id).one()
    del_episode = session.query(Episode).filter_by(id=episode_id).one()
    if request.method == 'POST':
        session.delete(del_episode)
        session.commit()
        flash('Episode Successfully Deleted')
        return redirect(url_for('showEpisodes', tvshow_id=tvshow_id))
    else:
        return render_template('deleteepisode.html', episode=del_episode)


# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        del login_session['username']
        del login_session['credentials']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully been logged out.")
        return redirect(url_for('showTvshows'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showTvshows'))


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
