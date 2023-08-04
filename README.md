# 🔎 Tool for Employee Information Gathering

This is a tool designed for Open Source Intelligence (OSINT) purposes, which helps to gather information about employees of a company.

## 🚀 How it Works

The tool starts by searching through LinkedIn to obtain a list of employees of the company. Then, it looks for their social network profiles to find their personal email addresses. Finally, it uses those email addresses to search through  a custom COMB database to retrieve leaked passwords. You an easily add yours and connect to through the tool.

## 💻 Installation

To use this tool, you'll need to have Python 3.10 installed on your machine. Clone this repository to your local machine and install the required dependencies using pip in the *cli* folder:

pip install -r requirements.txt

### OSX
We know that there is a problem when installing the tool due to the *psycopg2* binary. If you run into this problem, you can solve it running:

python3 -m pip install psycopg2-binary


## 📈 Basic Usage

To use the tool, simply run the following command:

python3 cli/emploleaks.py

If everything went well during the installation, you will be able to start using EmploLeaks:

```
___________              .__         .__                 __
\_   _____/ _____ ______ |  |   ____ |  |   ____ _____  |  | __  ______
 |    __)_ /     \____  \|  |  /  _ \|  | _/ __ \__   \ |  |/ / /  ___/
 |        \  Y Y  \  |_> >  |_(  <_> )  |_\  ___/ / __ \|    <  \___ \
/_______  /__|_|  /   __/|____/\____/|____/\___  >____  /__|_ \/____  >
        \/      \/|__|                         \/     \/     \/     \/

OSINT tool 🕵  to chain multiple apis
emploleaks>
```

Right now, the tool supports two functionalities:
 - Linkedin, for searching all employees from a company and get their personal emails.
    - A GitLab extension, which is capable of finding personal code repositories from the employees.
 - If defined and connected, when the tool is gathering employees profiles, a search to a COMB database will be made in order to retrieve leaked passwords.


### Retrieving Linkedin Profiles

First, you must set the plugin to use, which in this case is *linkedin*. After, you should set your credentials and the run the *login* proccess:


emploleaks> use --plugin linkedin
emploleaks(linkedin)> setopt USER myemail@domain.com
[+] Updating value successfull
emploleaks(linkedin)> setopt PASS mypass1234
[+] Updating value successfull
emploleaks(linkedin)> show options
Module options:

Name    Current Setting     Required    Description
------  ------------------  ----------  ---------------------------
USER    myemail@domain.com  yes         linkedin account's username
PASS    ********          yes           linkedin accout's password
hide    yes                 no          hide the password field
emploleaks(linkedin)> run login
[+] Session established.

Now that the module is configured, you can run it and start gathering information from the company:

emploleaks(linkedin)> run find EvilCorp
[+] Added 25 new names.
[+] Added 22 new names.
🦄 Listing profiles:
🔑 Getting and processing contact info of "XYZ ZYX"
	Contact info:
	email: xya@gmail.com
	full name: XYZ XYZ
	profile name: xyz-xyz
	occupation: Sr XYZ
	public identifier: xyz-zyx
	urn: urn:li:member:67241221


### Get Linkedin accounts + Leaked Passwords

We created a custom *workflow*, where with the information retrieved by Linkedin, we try to match employees' personal emails to potential leaked passwords. In this case, you can connect to a database (in our case we have a custom indexed COMB database) using the *connect* command, as it is shown below:

emploleaks(linkedin)> connect --user myuser --passwd mypass123 --dbname mydbname --host 1.2.3.4
[+] Connecting to the Leak Database...
[*] version: PostgreSQL 12.15

Once it's connected, you can run the *workflow*. With all the users gathered, the tool will try to search in the database if a leaked credential is affecting someone:

emploleaks(linkedin)> run_pyscript workflows/check_leaked_passwords.py EvilCorp
[-] Failing login... trying again!
[-] Failing login... trying again!
[+] Connected to the LinkedIn api successfull
The following command could take a couple of minutes, be patient
🦄 Listing profiles:
🔑 Getting and processing contact info of "XYZ ZXY"
🔑 Getting and processing contact info of "YZX XZY"
🔑 Getting and processing contact info of "ZYX ZXY"
[...]
[+] Password for "XYZ ZXY" exists
[*] Email: xyzzxy@gmail.com
+------------------+
| passwords leaked |
+------------------+
| laFQqAOSL6t      |
+------------------+

As a conclusion, the tool will generate a console output with the following information:

- A list of employees of the company (obtained from LinkedIn)
- The social network profiles associated with each employee (obtained from email address)
- A list of leaked passwords associated with each email address.

## 📌 Next Steps

We are integrating other public sites and applications that may offer about a leaked credential. We may not be able to see the plaintext password, but it will give an insight if the user has any compromised credential:
 
 - Integration with Have I Been Pwned?
 - Integration with Firefox Monitor
 - Integration with Leak Check
 - Integration with BreachAlarm

 Also, our idea is collect even more information from public sources from every employee. Do you have any idea in mind? Don't hesitate to reach us:

 Javi Aguinaga: jaguinaga@faradaysec.com
 Gabi Franco: gabrielf@faradaysec.com

 Or you con DM at @pastacls or @gaaabifranco on Twitter.

## 📝 License

This tool is licensed under the MIT License. See the `LICENSE` file for more information.
