import os, hashlib, sqlite3, re, requests
from flask import Flask, request, session, url_for, redirect, render_template, abort, g, flash, _app_ctx_stack
from datetime import datetime



app = Flask(__name__)

app.config['SECRET_KEY'] = 'development key'

class User():
    def __init__(self, username, password, email, creationTime = None):
        self.username = username
        self.password = password
        self.email = email
        self.creationTime = creationTime

    def __str__(self):
        return F"User Object: {self.username}, password: [...], email: {self.email}"

    def fromDB(data_row):
        # static function: creates User object from database entry
        username, email, password, creationTime = data_row
        return User(username, password, email, creationTime)

class Review():
    def __init__(self, id, gameName, user, date, rating, review):
        self.id = id
        self.gameName = gameName
        self.user = user
        if date:
            self.date = date.split(" ", 1)[0]
        else:
            self.date = "NULL"
        self.rating = rating 
        self.review = review

class Game():
    def __init__(self, title, desc, genreid, gameid, release_date, title_cleaned):
        self.title = title
        self.desc = desc
        self.release_date = release_date
        self.genre = "None"
        self.id = gameid
        self.title_cleaned = title # clean apostraphes
        self.img = "https://cdn.thegamesdb.net/images/original/boxart/front/{}-1.jpg".format(gameid)
        self.alt_img = "https://cdn.thegamesdb.net/images/original/boxart/front/{}-2.jpg".format(gameid)

        for key in Database.genre_mappings.keys():
            if Database.genre_mappings[key] in genreid:
                if self.genre == "None":
                    self.genre = key
                else:
                    self.genre += (', ' + key)

    def fromDB(data_row):
        genreids = [int(val) for val in data_row[12].strip('][').split(', ')] if data_row[12] != 'None' else []
        return Game(data_row[1], data_row[6], genreids, data_row[0], data_row[2], "")
        
class Database():
    genre_mappings = { # maps a readable genre to the genre id number, currently genre names are g_ as i dont know what the mapping is
        'Action' : 1,
        'Adventure' : 2,
        'Construction and Management Sim' : 3,
        'RPG' : 4,
        'Puzzle' : 5,
        'Strategy' : 6,
        'Racing' : 7,
        'Shooter' : 8,
        'Life Sim' : 9,
        'Fighting' : 10,
        'Sports' : 11,
        'Sandbox' : 12,
        'Flight Sim' : 13,
        'MMO' : 14,
        'Platformer' : 15,
        'Stealth' : 16,
        'Music' : 17,
        'Horror' : 18,
        'Vehicle Sim' : 19,
        'Board Game' : 20,
        'Education' : 21,
        'Family' : 22,
        'Party' : 23,
        'Productivity' : 24,
        'Quiz' : 25,
        'Utility' : 26,
        'Virtual Console' : 27,
        'Unofficial' : 28,
        'GBA Video / PSP Video' : 29
    }

    def get(query):
        con = sqlite3.connect('database.db') 
        cur = con.cursor() 
        cur.execute(query)
        all_rows = cur.fetchall()
        con.close()
        if (len(all_rows) == 0): # Username not found in database
            return None
        else:
            return all_rows

    def post(query):
        con = sqlite3.connect('database.db') 
        cur = con.cursor()

        cur.execute(query)
        con.commit()
        con.close()

    def addFriend(self, fromUser, toUser):
        query = """INSERT INTO friends(fromUser, toUser) 
                   VALUES('{}','{}')""".format(fromUser, toUser)
        Database.post(query)
    
    def getFriend(self, fromUser, toUser):
        query="""SELECT * FROM friends WHERE fromUser = '{}' AND toUser = '{}'""".format(fromUser, toUser)
        all_rows = Database.get(query)
        return all_rows

    def getAllFriends(self, fromUser):
        query="""SELECT toUser FROM friends WHERE fromUser = '{}'""".format(fromUser)
        all_rows = Database.get(query)
        return all_rows

    def getAllFriendsTo(self, toUser):
        query="""SELECT fromUser FROM friends WHERE toUser = '{}'""".format(toUser)
        all_rows = Database.get(query)
        return all_rows

    def addUser(self, userObject):
        query = """INSERT INTO users(user_id, email, password, join_date) 
                   VALUES('{}','{}','{}','{}')""".format(userObject.username, userObject.email, userObject.password, datetime.today())
        Database.post(query)

    def getUser(self, username):
        query="""SELECT * FROM users WHERE user_id = '{}'""".format(username)
        all_rows = Database.get(query)
        return User.fromDB(all_rows[0]) if all_rows and len(all_rows) > 0 else None

    def getAllReviews(self, username): # returns all reviews for a user
        query="""SELECT * FROM reviews WHERE user = '{}'""".format(username)
        all_rows = Database.get(query)
        return [Review(*data_row) for data_row in all_rows] if all_rows and len(all_rows) > 0 else []

    def getUserReview(self, username, title): # returns a review if the user has reviewed the game
        query="""SELECT * FROM reviews WHERE user = '{}' AND gameName = '{}'""".format(username, title)
        all_rows = Database.get(query)
        return [Review(*data_row) for data_row in all_rows] if all_rows and len(all_rows) > 0 else []
        
    def getReviews(self, gameName): # returns all reviews for a game
        query="""SELECT * FROM reviews WHERE gameName = '{}'""".format(gameName)
        all_rows = Database.get(query)
        return [Review(*data_row) for data_row in all_rows] if all_rows and len(all_rows) > 0 else []

    def postReview(self, reviewObject):
        query = """INSERT INTO reviews(gameName, user, date, rating, review) 
                   VALUES('{}','{}','{}','{}','{}')""".format(reviewObject.gameName, reviewObject.user.username, datetime.today(), reviewObject.rating, reviewObject.review)
        Database.post(query)

    def getGenre(self, genreids):
        if genreids == None:
            return []
            
        if type(genreids) != list:
            genreids = [genreids]

        all_rows = []
        for genreid in genreids:
            query=F"""SELECT * FROM games WHERE genres LIKE '%{genreid}%' LIMIT 100"""
            all_rows += Database.get(query)

        for data_row in all_rows: # the search query will also return things like genre = 12 when searching for genre = 1 due to the way string matching works
            genreids = [int(val) for val in data_row[12].strip('][').split(', ')] if data_row[12] != 'None' else []
            if int(genreid) not in genreids:
                all_rows.remove(data_row)

        
        return [Game.fromDB(data_row) for data_row in all_rows][:50] if all_rows and len(all_rows) > 0 else []

    def getGame(self, title, exact = False):
        if exact:
            query=F"""SELECT * FROM games WHERE game_title = '{title}'"""
        else:
            query=F"""SELECT * FROM games WHERE game_title LIKE '%{title.lower()}%'"""

        all_rows = Database.get(query)
        return [Game.fromDB(data_row) for data_row in all_rows] if all_rows and len(all_rows) > 0 else []

    def deleteAllUsers(self):
        print("TODO: implement Database.deleteAllUsers")

    def getRandGame(self):
        query="""SELECT * FROM GAMES WHERE rowid = (ABS(RANDOM()) % (SELECT (SELECT MAX(rowid) FROM games)+1))"""
        all_rows = Database.get(query)
        return all_rows[0]
        
def hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

db = Database()

@app.cli.command('initdb')
def initdb_command():
    # Reinitialize the database tables
    db.deleteAllUsers()
    print('Initialized Database')

@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = db.getUser(session['user_id'])

@app.route('/')
def default():
    if 'user_id' in session:
        return redirect(url_for('home'))
    g.user = None
    return render_template('layout.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect('/')
    
    return render_template('layout.html')

@app.route('/profile/<path:user>', methods=['GET', 'POST'])
def profile(user):
    error = None
    if not db.getUser(user):
        error = 'User does not exist'
    userReviews = db.getAllReviews(user)
    friends = db.getAllFriends(user)
    potential_friends = db.getAllFriendsTo(user)
    potential_friends_list = []
    incoming_friends = [] # friend requests the user hasn't accepted
    true_friends = [] # true_friends = friends that have added the user back
    pending_friends = [] # users that have been sent a friend request but haven't accepted yet
    friends_list = [] # all users that the user has sent a friend request to

    if potential_friends is not None:
        for friend in potential_friends:
                potential_friends_list.append(friend[0])
                
        for friend in potential_friends_list:
            if db.getFriend(user, friend) is None:
                incoming_friends.append(friend)

    if friends is not None:
        for friend in friends:
            friends_list.append(friend[0])

        for friend in friends_list:
            if db.getFriend(friend, user) is not None:
                true_friends.append(friend)
            else:
                pending_friends.append(friend)

    if request.method == 'POST':
        friend = request.form['friend']
        if len(friend) == 0:
            error = 'User not specified.'
        elif db.getFriend(user, friend):
            error = 'You are already friends with {}.'.format(friend)
        elif db.getUser(friend) is None:
            error = 'User does not exist.'
        elif friend == user:
            error = 'You cannot send yourself a friend request.'
        else:
            db.addFriend(user, friend)
            flash('Friend request sent')
    return render_template('profile.html', error=error, user=user, userReviews = userReviews, friends=true_friends, pending_friends = pending_friends, incoming_friends = incoming_friends)

@app.route('/random', methods=['GET'])
def random():
    game = db.getRandGame()
    return redirect(F'/game/{game[1]}')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Logs the user in."""
    if g.user:
        return redirect(url_for('home'))
    error = None
    if request.method == 'POST':
        user = db.getUser(request.form['username'])
        if user is None:
            error = 'Invalid username'
        elif user.password != hash(request.form['password']):
            error = 'Invalid password'
        else:
            flash('You were logged in')
            session['user_id'] = user.username
            return redirect(url_for('home'))
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registers the user."""
    if g.user:
        return redirect(url_for('home'))
    error = None
    if request.method == 'POST':
        if not request.form['username']:
            error = 'You have to enter a username'
        elif not request.form['password']:
            error = 'You have to enter a password'
        elif request.form['password'] != request.form['password2']:
            error = 'The two passwords do not match'
        elif db.getUser(request.form['username']) is not None:
            error = 'The username is already taken'
        else:
            hashedPassword = hash(request.form['password'])
            newUser = User(request.form['username'], hashedPassword, request.form['email'])
            db.addUser(newUser)
            flash('You were successfully registered and can login now')
            return redirect(url_for('login'))
    return render_template('register.html', error=error, header="Sign Up")

@app.route('/search', methods=['GET', 'POST'])
def search():
    query = request.args.get('search', None)
    query = query.replace("'", "''")
    if query == "" or query == None:
        flash("Please enter a valid title")
        return redirect('/')
        
    if query.startswith('genre:'):
        return redirect(F'/search/genre/{query.replace("genre:", "", 1)}')
    
    return redirect(F'/search/title/{query}')

@app.route('/search/genre/<path:genre>', methods=['GET'])
def search_genre(genre):
    genreids = []
    for key, value in Database.genre_mappings.items():
       if genre.lower() in key.lower():
            genreids.append(value) 
            
        
    games = db.getGenre(genreids)
    games = removeDuplicates(games)
    return render_template('search_results.html', header = genre, games = games)

@app.route('/search/title/<path:title>', methods=['GET'])
def search_title(title):
    games = db.getGame(title)
    games = removeDuplicates(games)
    title = title.replace("''", "'")
    for game in games:
        game.title_cleaned = game.title.replace("'","''")
    return render_template('search_results.html', header = title, games = games)

def removeDuplicates(games):
    hashTable = {}

    for game in games:
        if game.title.lower() not in hashTable:
            hashTable[game.title.lower()] = game

    return hashTable.values()



@app.route('/game/<path:gameName>', methods=['GET', 'POST'])
def game(gameName):
    gameName = gameName.replace("''", "'")
    gameName = gameName.replace("'", "''")
    if db.getGame(gameName, exact = True) == []:
        return render_template('game_not_found.html', header = gameName)
    
    if request.method == 'POST':
        if not g.user:
            flash("You must be logged in to post a review")
        if g.user and db.getUserReview(g.user.username, gameName):
            flash("You cannot leave multiple reviews for one game")
        elif g.user:
            newReview = Review(None, gameName, g.user, None, request.form['rate'], request.form['review'])
            db.postReview(newReview)

    game_image = db.getGame(gameName, exact = True)[0].id
    game_desc = db.getGame(gameName, exact = True)[0].desc

    reviews = db.getReviews(gameName)

    if not reviews:
        star_rate = "Not rated, be the first!"
    else:
        star_rate = ""
        total_rev_score = 0
        rev_count = 0
        for review in reviews: 
            total_rev_score += review.rating
            rev_count += 1
        avg_score = total_rev_score/rev_count
        avg_score = round(avg_score, ndigits=None)
        for i in range(avg_score):
            star_rate = star_rate + " ★ "
        for j in range(5-avg_score):
            star_rate = star_rate + " ☆ "

    internal_name = re.sub(r'\W+', '', gameName.replace(" ", "_"))
    file_address = "https://cdn.thegamesdb.net/images/original/boxart/front/{}-1.jpg".format(game_image)

    try:
        resp = requests.get(file_address)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as err:
        file_address = "https://cdn.thegamesdb.net/images/original/boxart/front/{}-2.jpg".format(game_image)
    gameName = gameName.replace("''", "'")
    return render_template('game.html', desc = game_desc, average_rating = star_rate, header = gameName, reviews = reviews, internal_name = gameName, file_address = file_address)

@app.route('/logout')
def logout():
    """Logs the user out."""
    flash('You were logged out')
    session.pop('user_id', None)
    return redirect(url_for('home'))

@app.route('/feed', methods=['GET'])
def feed():
    if not g.user:
        flash("You must log in to view this page")
        return redirect('/')
   
    user = g.user.username
    error = None
    if not db.getUser(user):
        error = 'Please login to see your feed'
    userReviews = db.getAllReviews(user)
    friends = db.getAllFriends(user)

    true_friends = [] # true_friends = friends that have added the user back
    friends_list = [] # all users that the user has sent a friend request to

    if friends is not None:
        for friend in friends:
            friends_list.append(friend[0])

        for friend in friends_list:
            if db.getFriend(friend, user) is not None:
                true_friends.append(friend)
    reviews = []
    for friend in true_friends:
        review = db.getAllReviews(friend)
        if review is not None:
            reviews.append(review)

    return render_template('feed.html', friends = true_friends, reviews = reviews)
