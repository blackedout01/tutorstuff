import sys, os, json, re
from dataclasses import dataclass

# NOTE(blackedout): If you are using a gpg key to sign your commits you might want to run
# gpg -s --default-key <your extra extra very very long key id> signtest
# before running the commit command in COMMIT mode, such that the script doesn't get interrupted with a passphrase dialog

# MARK: CONFIG

# NOTE(blackedout): URL to the gitlab server where the projects live, e.g. "https://gitlab.abc.net"
GITLAB_SERVER_URL = ""

# NOTE(blackedout): File name that contains just the read access token you created in your gitlab account settings
TOKEN_FILENAME = "token"

# NOTE(blackedout): The id of the group where the projects live, must be an integer
GROUP_ID = 0

# NOTE(blackedout): Regex pattern to filter the projects of the group.
# For example if the group contains the projects tutor0-group0, tutor0-group1, tutor1-group0, tutor1-group1
# and you are only assigned the ones with tutor1 prefix, you could set this to "tutor1-group[0-9]+"
PROJECT_NAME_PATTERN_STRING = ""

# NOTE(blackedout): The name of the file that will store group info such as name, ssh project url and scored commit ids
REPOS_JSON_FILENAME = "repos.json"

# NOTE(blackedout): Prefix of the files where you will put in the rating of each group (comments and scored points)
# IMPORTANT: MUST BE CONSISTENT FOR ALL RATING FILES
RATINGS_FILEPREFIX = "r"

TASK_STRING = "Aufgabe"
SUM_STRING = "Summe"
TOTAL_STRING = "Gesamt"
SHEET_STRING = "Blatt"
MASTER_STRING = "Master"
MAX_STRING = "Max"
PERCENT_STRING = "%"
SCORED_STRING = "Erreicht"
TOTAL_SCORE_STRING = "Gesamtpunktzahlen"
SEE_PDF_STRING = "Siehe Anmerkungen in ``."
CORRECTION_STRING = "Korrektur"
POINTS_FROM_STRING = lambda points: float(points.replace(",", "."))
POINTS_TO_STRING = lambda points: f"{points:g}"


# MARK: UTIL
@dataclass
class Command:
    name: str
    f: callable
    arg_names: list[str]
    repeat_last_arg: bool
    example_usage: str|None


@dataclass
class Score:
    num: float
    max: float
    num_master: float
    max_master: float


def print_exit(message: str):
    print(message)
    sys.exit()


def parse_bew_file(blatt_num):
    bew_strings = {}
    scores = {}
    with open(f"{RATINGS_FILEPREFIX}{blatt_num:02d}.md", "r") as file:
        lines = file.readlines()

        curr_group = None
        bew_string = None
        max_aufgaben_scores = None
        group_aufgaben_string = None
        group_punkte_string = None
        group_score = {}

        def end_group(max_aufgaben_scores):
            bew_strings[curr_group] = bew_string.strip()
            scores[curr_group] = Score(*group_score["g"], *(group_score["m"] if "m" in group_score else (0.0, 0.0)))

            score_sum = 0.0
            max_score_sum = 0.0
            group_max_aufgaben_scores = {}
            for ex_key, (score, max_score) in group_score.items():
                if isinstance(ex_key, int):
                    score_sum += score
                    max_score_sum += max_score
                group_max_aufgaben_scores[ex_key] = max_score
            if score_sum != group_score["g"][0]:
                print(f"SCORE MISMATCH {blatt_num} {curr_group}")
            if max_score_sum != group_score["g"][1]:
                print(f"MAX SCORE MISMATCH {blatt_num} {curr_group}")

            if max_aufgaben_scores is None:
                max_aufgaben_scores = group_max_aufgaben_scores
            else:
                assert(max_aufgaben_scores == group_max_aufgaben_scores)

        for i in range(len(lines)):
            line = lines[i]
            matched = re.match(f"^# ({PROJECT_NAME_PATTERN_STRING})", line)
            if matched:
                if bew_string:
                    end_group(max_aufgaben_scores)

                curr_group = matched.group(1)
                bew_string = ""
                group_blatt_num_line = None
            elif curr_group:
                bew_string += line

                if not group_blatt_num_line:
                    title_match = re.match(f"### {SHEET_STRING} ([0-9]+)", line)
                    if title_match:
                        group_blatt_num = int(title_match.group(1))
                        group_blatt_num_line = i
                        assert(group_blatt_num == blatt_num)
                elif i == group_blatt_num_line + 1:
                    group_aufgaben_string = line
                elif i == group_blatt_num_line + 3:
                    group_punkte_string = line
                    
                    group_aufgaben_split = re.split(r"\s*\|\s*", group_aufgaben_string)[1:-1]
                    group_punkte_split = re.split(r"\s*\|\s*", group_punkte_string)[1:-1]
                    assert(len(group_aufgaben_split) == len(group_punkte_split))

                    group_score = {}
                    for j in range(len(group_aufgaben_split)):
                        aufgabe_name = group_aufgaben_split[j]
                        punkte_string = group_punkte_split[j]

                        punkte_match = re.match(r"\*\*(\d+[,\.]?\d*)\/(\d+[,\.]?\d*)\*\*", punkte_string)
                        assert(punkte_match)
                        this_score = POINTS_FROM_STRING(punkte_match.group(1))
                        max_score = POINTS_FROM_STRING(punkte_match.group(2))
                        aufgabe_match = re.match(rf"{TASK_STRING} (\d+)", aufgabe_name)
                        gesamt_match = re.match(TOTAL_STRING, aufgabe_name)
                        master_match = re.match(MASTER_STRING, aufgabe_name)
                        if aufgabe_match:
                            aufgabe_num = int(aufgabe_match.group(1))
                            group_score[aufgabe_num] = (this_score, max_score)
                        elif gesamt_match:
                            group_score["g"] = (this_score, max_score)
                        elif master_match:
                            group_score["m"] = (this_score, max_score)
        end_group(max_aufgaben_scores)
    return bew_strings, scores


def gen_markdown_lr(scores: list[Score], add_master_points: bool=False, append_note: bool=False, print_summary: bool=False):
    max_label = f"**{MAX_STRING}**"
    percent_label = f"**{PERCENT_STRING}**"

    sum_score = Score(
        num=sum([s.num for s in scores]),
        max=sum([s.max for s in scores]),
        num_master=sum([s.num_master for s in scores if s.num_master is not None]),
        max_master=sum([s.max_master for s in scores if s.num_master is not None])
    )

    def dash_entry(width: int):
        return f"| :{'-'*(width - 2)}: "
    
    def content_entry(content: str, width: int, center: bool=False):
        return f"| {content:{'^' if center else '>'}{width}} "

    def points_entry(points: float|None, width: int, bold: bool=False, prefix: str=""):
        bold_fix = "**" if bold else ""
        content = f"{bold_fix}{points:g}{bold_fix}".replace(".", ",") if points is not None else ""
        return f"| {prefix}{content:>{width-len(prefix)}} "
    
    def percent_entry(frac: float|None, width: int, bold: bool=False):
        bold_fix = "**" if bold else ""
        content = f"{bold_fix}{frac*100:.3g}{bold_fix}".replace(".", ",") if frac is not None else ""
        return content_entry(content, width)
    
    lbl_colwidth = 12
    num_colwidth = 5
    sum_colwidth = 8

    markdown = f"### {TOTAL_SCORE_STRING}\n"
    markdown += content_entry(SHEET_STRING, lbl_colwidth, center=True) + "".join([content_entry(f"{i + 1:2}", num_colwidth, center=True) for i in range(len(scores))]) + content_entry(SUM_STRING, sum_colwidth, center=True) + "|\n"
    markdown += dash_entry(lbl_colwidth) + dash_entry(num_colwidth)*len(scores) + dash_entry(sum_colwidth) + "|\n"
    markdown += content_entry(f"**{SCORED_STRING}**", lbl_colwidth) + "".join([points_entry(s.num, num_colwidth) for s in scores]) + points_entry(sum_score.num, sum_colwidth, bold=True) + "|\n"
    markdown += content_entry(max_label, lbl_colwidth) + "".join([points_entry(s.max, num_colwidth) for s in scores]) + points_entry(sum_score.max, sum_colwidth, bold=True) + "|\n"
    markdown += content_entry(percent_label, lbl_colwidth) + "".join([percent_entry(s.num/s.max, num_colwidth) for s in scores]) + percent_entry(sum_score.num/sum_score.max, sum_colwidth, bold=True) + "|\n"
    
    if print_summary:
        bachelor_percent = sum_score.num/sum_score.max*100
        print(f"{sum_score.num:g}/{sum_score.max:g} Punkte ({bachelor_percent:.3g} %)")
        if sum_score.max_master > 0:
            master_percent = sum_score.num_master/sum_score.max_master*100
            print(f"{sum_score.num_master:g}/{sum_score.max_master:g} Masterpunkte ({master_percent:.3g} %)")
        zulassung_string = "KEINE ZULASSUNG"
        if bachelor_percent >= 50.0:
            if sum_score.max_master > 0 and master_percent >= 50.0:
                zulassung_string = "Masterzulassung"
            else:
                zulassung_string = "Bachelorzulassung"
        print(f"=> {zulassung_string}")
        print()

    if sum_score.max_master > 0:
        if add_master_points:
            master_prefix = "+"
            num_cols_string = "".join([percent_entry((s.num + s.num_master)/(s.max + s.max_master), num_colwidth) for s in scores])
            sum_col_string = percent_entry((sum_score.num + sum_score.num_master)/(sum_score.max + sum_score.max_master), sum_colwidth, bold=True)
        else:
            master_prefix = " "
            num_cols_string = "".join([percent_entry(s.num_master/s.max_master if s.max_master > 0.0 else None, num_colwidth) for s in scores])
            sum_col_string = percent_entry(sum_score.num_master/sum_score.max_master, sum_colwidth, bold=True)
        
        markdown += content_entry(f"**{MASTER_STRING}**", lbl_colwidth) + "".join([points_entry(s.num_master, num_colwidth, prefix=master_prefix) for s in scores]) + points_entry(sum_score.num_master, sum_colwidth, bold=True) + "|\n"
        markdown += content_entry(max_label, lbl_colwidth) + "".join([points_entry(s.max_master, num_colwidth, prefix=master_prefix) for s in scores]) + points_entry(sum_score.max_master, sum_colwidth, bold=True) + "|\n"
        markdown += content_entry(percent_label, lbl_colwidth) + num_cols_string + sum_col_string + "|\n"

    if append_note:
        master_row_spec = "zweite" if add_master_points else "**beide**"
        markdown += f"\n**Wichtig**: Für < 50 % der Punkte in Summe nach Bewertung des letzten Blatts (Bachelor: erste %-Zeile, Master: {master_row_spec} %-Zeilen) ist dieses Klausurzulassungskriterium nicht erfüllt.\n"
    
    return markdown


def parse_sheet_number(arg: str):
    try:
        blatt_num = int(arg)
    except:
        print_exit(f"'{arg}' is not a valid sheet number.")
    return blatt_num


# MARK: COMMAND get
def get_repos(command: Command, args: list[str]):
    import gitlab

    with open(TOKEN_FILENAME) as token_file:
        gitlab_token = token_file.read()
    
    gl = gitlab.Gitlab(url=GITLAB_SERVER_URL, private_token=gitlab_token)
    group = gl.groups.get(GROUP_ID)
    group_projects = group.projects.list(get_all=True, iterator=True)

    project_urls = []
    for gp in group_projects:
        project = gl.projects.get(gp.get_id())
        if re.match(f"^{PROJECT_NAME_PATTERN_STRING}", project.name):
            project_urls.append({ "name": project.name, "ssh": project.ssh_url_to_repo })

    project_urls.sort(key=lambda x: x["ssh"])
    with open(REPOS_JSON_FILENAME, "w", encoding="utf-8") as file:
        json.dump(project_urls, file, ensure_ascii=False, indent=4)


# MARK: COMMAND clone
def clone_repos(command: Command, args: list[str]):
    data = json.load(open(REPOS_JSON_FILENAME))
    for repo in data:
        url = repo["ssh"]
        os.system("git clone " + url)


# MARK: COMMAND pull
def pull_repos(command: Command, args: list[str]):
    data = json.load(open(REPOS_JSON_FILENAME))
    for repo in data:
        dir = repo["name"].split()[0]
        print(dir)
        os.system(f"cd {dir} && git pull")


# MARK: COMMAND saveh
def save_hashes(command: Command, args: list[str]):
    import git

    blatt_num = parse_sheet_number(args[0])

    repos = json.load(open(REPOS_JSON_FILENAME))
    for repo in repos:
        dir = repo["name"].split()[0]
        print(dir)

        g = git.Git(dir)
        commit_hash = g.log("--format=%H", "-n 1")
        if str(blatt_num) in repo:
            print_exit(f"Commit hash for sheet {blatt_num} already saved.")
        else:
            repo[str(blatt_num)] = commit_hash

    with open(REPOS_JSON_FILENAME, "w", encoding="utf-8") as file:
        json.dump(repos, file, ensure_ascii=False, indent=4)


# MARK: COMMAND commit
def commit_repos(command: Command, args: list[str]):
    @dataclass
    class GroupData:
        bew_strings: list[str]
        scores: list[Score]

    sheet_number = parse_sheet_number(args[0])

    repos = json.load(open(REPOS_JSON_FILENAME))
    for repo in repos:
        repo["dirname"] = repo["name"].split(" ")[0]
    group_data = { repo["dirname"]: GroupData([], []) for repo in repos }
    group_names = { repo["dirname"]: repo["name"] for repo in repos }

    for i in range(1, sheet_number + 1):
        bew_strings, scores = parse_bew_file(i)

        for repo in repos:
            repo_dirname = repo["dirname"]
            if repo_dirname not in bew_strings:
                print_exit(f"ERROR: Missing bew_string for group {repo_dirname}")
            if repo_dirname not in scores:
                print_exit(f"ERROR: Missing scores for group {repo_dirname}")
            commit_hash_key = str(i)
            if commit_hash_key not in repo:
                print_exit(f"ERROR: Missing commit hash for group {repo_dirname}")
            
            commit_hash = repo[str(i)]
            bew_string = bew_strings[repo_dirname].replace("Commit \n", f"Commit {commit_hash}\n")
            group_data[repo_dirname].bew_strings.append(bew_string)
            group_data[repo_dirname].scores.append(scores[repo_dirname])

    for repo_dirname, data in group_data.items():
        readme_start = ""
        readme_path = os.path.join(repo_dirname, "README.md")
        with open(readme_path, "r") as file:
            lines = file.readlines()
            for line in lines:
                bew_start_match = re.match(rf"### (?:{SHEET_STRING} \d+|{TOTAL_SCORE_STRING})", line)
                if bew_start_match:
                    break
                readme_start += line

        if args[1] == "SUMMARY":
            print(group_names[repo_dirname])
            gen_markdown_lr(data.scores, add_master_points=False, append_note=False, print_summary=True)
        else:
            print_instead_of_readme = False
            if print_instead_of_readme:
                x = ""
                x += (readme_start)
                x += gen_markdown_lr(data.scores, add_master_points=False, append_note=False)
                for bew_string in reversed(data.bew_strings):
                    x += ("\n\n" + bew_string + "\n")
                x += ("\n")
                print(x)
            else:
                print(readme_path)
                with open(readme_path, "w") as file:
                    file.write(readme_start)
                    file.write(gen_markdown_lr(data.scores, add_master_points=False, append_note=False))
                    for bew_string in reversed(data.bew_strings):
                        file.write("\n\n" + bew_string)
                    file.write("\n")

            if args[1] == "COMMIT":
                cd_prefix = f"cd {repo_dirname} &&"
                #os.system(f"{cd_prefix} git checkout korrektur || git checkout -b korrektur")
                os.system(f"{cd_prefix} git stash")
                os.system(f"{cd_prefix} git pull")
                os.system(f"{cd_prefix} git stash pop")

                os.system(f"{cd_prefix} git add README.md \\*.pdf")
                os.system(f"{cd_prefix} git restore .")
                os.system(f"{cd_prefix} git commit -m \"{CORRECTION_STRING} {SHEET_STRING} {sheet_number}\"")
                os.system(f"{cd_prefix} git push -u origin main")


# MARK: COMMAND rmd
def create_ratings_md(command: Command, args: list[str]):
    sheet_number = args[0]
    try:
        sheet_number = int(sheet_number)
    except:
        print_exit(f"Invalid sheet number '{sheet_number}' (not an integer).")

    task_summary_lines = ["|" for _ in range(3)]
    task_details = ""
    
    def append_task(task_name, task_points):
        task_points_string = POINTS_TO_STRING(task_points)
        task_points_zero = f"**{POINTS_TO_STRING(POINTS_FROM_STRING("0"))}/{task_points_string}**"
        task_points_max = f"**{task_points_string}/{task_points_string}**"
        max_length = max(len(task_name), len(task_points_max))

        task_summary_lines[0] += f" {task_name:^{max_length}} |"
        task_summary_lines[1] += f" :{'-'*(max_length - 2)}: |"
        task_summary_lines[2] += f" {task_points_zero:^{max_length - (len(task_points_max) - len(task_points_zero))}} |"

    points_sum = POINTS_FROM_STRING("0")
    for task_arg in args[1:]:
        task_split = task_arg.split(":")
        if len(task_split) != 3:
            print_exit(f"Task argument '{task_arg}' invalid (format must be <{command.arg_names[1]}>).")
        task, subtasks, points = task_split
        try:
            points = POINTS_FROM_STRING(points)
        except:
            print_exit(f"Task points '{points}' invalid.")
        points_sum += points

        task_name = f"{TASK_STRING} {task}"
        append_task(task_name, points)

        task_details += f"#### {task_name}"
        breaker = ""
        if subtasks == "FILE":
            task_details += f"\n{SEE_PDF_STRING}"
        else:
            for subtask in subtasks:
                task_details += f"\n{breaker}**{subtask})**"
                breaker = "<br/>"
        task_details += "\n\n"

    append_task(TOTAL_STRING, points_sum)

    template_string = f"### {SHEET_STRING} {sheet_number}\n"
    for a in task_summary_lines:
        template_string += f"{a}\n"
    template_string += f"\nCommit \n\n"
    template_string += task_details + "\n"

    md_string = f"# Template\n\n{template_string}"
    repos = json.load(open(REPOS_JSON_FILENAME))
    for repo in repos:
        dir = repo["name"].split()[0]
        md_string += f"# {dir}\n\n{template_string}"

    ratings_md_filename = f"{RATINGS_FILEPREFIX}{sheet_number:02d}.md"
    if os.path.exists(ratings_md_filename):
        print(f"File '{ratings_md_filename}' does already exist.")
        i = input("Overwrite [Y]? ")
        if i != "Y":
            sys.exit()
    with open(ratings_md_filename, "w") as ratings_md_file:
        ratings_md_file.write(md_string)


# MARK: MAIN
if __name__ == "__main__":
    commands = [
        Command("get", get_repos, [], False, None),
        Command("clone", clone_repos, [], False, None),
        Command("pull", pull_repos, [], False, None),
        Command("saveh", save_hashes, ["sheet number"], False, "saveh 1"),
        Command("commit", commit_repos, ["sheet number", "COMMIT if to be committed"], False, None),
        Command("rmd", create_ratings_md, ["sheet number", "task:subtasks:points"], True, "rmd 1 1:c:1 2:abcd:9 3:FILE:10"),
    ]

    def print_command_usage_exit(command: Command):
        args_string = " ".join([f"<{arg_name}>" for arg_name in command.arg_names])
        repeat_string = "..." if command.repeat_last_arg else ""
        print(f"Usage: {command.name} {args_string}{repeat_string}")
        if command.example_usage:
            print(f"Example: {command.example_usage}")
        sys.exit()

    was_command_found = False
    command_name = None
    if len(sys.argv) > 1:
        command_name = sys.argv[1]
        for command in commands:
            if command_name == command.name:
                if len(sys.argv) < 2 + len(command.arg_names):
                    print(f"Not enough arguments.")
                    print_command_usage_exit(command)
                if not command.repeat_last_arg and len(sys.argv) > 2 + len(command.arg_names):
                    print(f"Too many arguments.")
                    print_command_usage_exit(command)
                command.f(command, sys.argv[2:])
                was_command_found = True
    if not was_command_found:
        error_string = f"Unknown command '{command_name}'" if command_name else "No command specified"
        commands_string = ", ".join([command.name for command in commands])
        print_exit(f"{error_string}. Supported are {commands_string}")


