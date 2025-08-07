# tutorstuff

Some code to make grading submissions easier. I don't need this code anymore so if something doesn't work, feel free to make an issue or a pull request.

## who is this for

If you are a tutor and need to grade student submissions with the following properties:

* the projects are maintained on a GitLab server (that of your university)
* all student repositories are rooted in the same gitlab group that you know the id of
* there is **exactly one** repository for each student group that gets continuously updated with new exercise sheets and task code
* each one of these repositories contains a `README.md` which will be updated each time you grade an exercise sheet

## example output

Assuming there are two excerise sheets, this is what the rating could look like:

### Total scores
|   Sheet   |   1   |   2   |   Sum    |
| :-------: | :---: | :---: | :------: |
| **Score** |    15 |    10 |   **25** |
|   **Max** |    20 |    10 |   **30** |
|     **%** |    75 |   100 | **83,3** |


### Sheet 2
| Task 1  | Task 2  |   Total   |
| :-----: | :-----: | :-------: |
| **5/5** | **5/5** | **10/10** |

Commit &lt;automatically inserted commit hash&gt;

#### Task 1
good

#### Task 2
epic


### Sheet 1
| Task 1  | Task 2  |  Task 3   |   Total   |
| :-----: | :-----: | :-------: | :-------: |
| **4/5** | **5/5** | **6/10**  | **15/20** |

Commit &lt;automatically inserted commit hash&gt;

#### Task 1
some comment, but not everything was correct **-1 P**

#### Task 2
bla

#### Task 3
bla **-4 P**


## before doing anything

The script you need to call when initiating some automation is `repos.py`.
Serveral constants are defined in the beginning that are meant to be modified to your liking.

The following ones must be set before doing anything:

```python
GITLAB_SERVER_URL = ""
TOKEN_FILENAME = "token"
GROUP_ID = 0
PROJECT_NAME_PATTERN_STRING = ""
REPOS_JSON_FILENAME = "repos.json"
RATINGS_FILEPREFIX = "r"
```

1. Set `GITLAB_SERVER_URL` to the URL to the GitLab server where the projects are maintained, e.g. `"https://gitlab.abc.net"`.
2. Go into your account settings and create a read only access token. Put the token code into the file named `TOKEN_FILENAME`. So if you want to use the default file name, put it in `token` in the same directory as the script, no file extensions.
3. Find the id of the group where all the student repositories lie and set `GROUP_ID` to it. Must be an integer.
4. The root group might contain repositories that were assigned to other tutors, so set the regex filter `PROJECT_NAME_PATTERN_STRING` such that only the respositories that were assigned to you are accepted.
5. Read the descriptions of the remaining constants in code and modify if you want to

## workflow

To create the repository info file and then and clone the repositoies (do these two only once)
```
python3 repos.py get
```
```
python3 repos.py clone
```

After the submission deadline has ended, pull the repositories:
```
python3 repos.py pull
```

Save the commit hashes of the version that you will grade, the integer is the sheet number:
```
python3 repos.py saveh 1
```

Create a rating template file, contains the template at the top and then configured for each group (the template part will be ignored). This is just an example, the first integer is the sheet number and the task format is `task-num:subtask-letters:points`:
```
python3 repos.py rmd 1 1:c:5 2:abcd:5 3:FILE:10
```

Commit once filled out, the integer is the sheet number (put anything but COMMIT at the end to just regenerate the README.md to take a look without committing immediately):
```
python3 repos.py commit 1 COMMIT
```
**IMPORTANT:** only README.md and any pdf file changes will be committed, anything else will be **discarded**.

