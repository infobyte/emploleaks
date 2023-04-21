# 🔎 Tool for Employee Information Gathering

This is a tool designed for Open Source Intelligence (OSINT) purposes, which helps to gather information about employees of a company.

## 🚀 How it Works

The tool starts by searching through LinkedIn to obtain a list of employees of the company. Then, it looks for their social network profiles to find their personal email addresses. Finally, it uses those email addresses to search through several websites (such as Have I Been Pwned and Firefox Monitor) and a custom COMB database to retrieve leaked passwords.

## 💻 Installation

To use this tool, you'll need to have Python 3.x installed on your machine. Clone this repository to your local machine and install the required dependencies using pip:

pip install -r requirements.txt


## 📈 Usage

To use the tool, simply run the following command:

python boom.py


The tool will generate a report with the following information:

- A list of employees of the company (obtained from LinkedIn)
- The social network profiles associated with each employee (obtained from email address)
- A list of leaked passwords associated with each email address (obtained from Have I Been Pwned, Firefox Monitor, and the custom COMB database)

## 📝 License

This tool is licensed under the MIT License. See the `LICENSE` file for more information.
