# Catalog Project
Nanodegree project #5
# Requirements
- [python2.7](https://www.python.org/)
- [vagrant](https://www.vagrantup.com/)
- [git](https://git-scm.com/)
- [virtualbox](https://www.virtualbox.org/)


## Download the source and VM configuration

From the terminal, run:
        
    git clone https://github.com/heyoni/nanodegree_five.git nanodegree_five

This will give you a directory named **nanodegree_five** complete with the source code for the flask application, a vagrantfile, and a 
bootstrap.sh file for installing all of the necessary tools. 

## Run the virtual machine!

Using the terminal, change directory to nanodegree (**cd nanodegree**), then type **vagrant up** to launch your virtual machine.


## Running the Restaurant Menu App
Once it is up and running, type **vagrant ssh**. This will log your terminal into the virtual machine, and you'll get a Linux shell prompt. 
When you want to log out, type **exit** at the shell prompt.  To turn the virtual machine off (without deleting anything), type **vagrant halt**. 
If you do this, you'll need to run **vagrant up** again before you can log into it.


Now that you have Vagrant up and running type **vagrant ssh** to log into your VM.  change to the /vagrant directory by typing **cd /vagrant**. 
This will take you to the shared folder between your virtual machine and host machine.

Type **ls** to ensure that you are inside the directory that contains project.py, database_setup.py, and two directories named 'templates' and 'static'

Now type **python database_setup.py** to initialize the database.

Type **python populatedb.py** to populate the database with TV Shows, their episodes and genres. Original Shows and Episodes will be owned by the user created during populatedb phase.

Type **python project.py** to run the Flask web server. In your browser visit **http://localhost:5000** to view the tvshows menu app.  
You should be able to view, add, edit, and delete tvshows, individual episodes as well as genres.
