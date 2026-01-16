SKILL_ONTOLOGY = {
    "cloud": {
        "aws", "amazon web services",
        "azure",
        "gcp", "google cloud platform", "google cloud",
        "digitalocean"
    },
    "ml": {
        "machine learning", "ml",
        "scikit-learn", "sklearn",
        "pytorch", "torch",
        "tensorflow", "keras",
        "xgboost", "lightgbm",
        "catboost"
    },
    "data_science": {
        "data science", "data scientist",
        "statistics", "statistical modeling",
        "hypothesis testing", "a/b testing",
        "time series", "forecasting"
    },
    "python": {
        "python", "python3",
        "flask", "django", "fastapi",
        "pandas", "numpy", "scipy",
        "matplotlib", "seaborn", "plotly"
    },
    "databases": {
        "sql", "nosql",
        "mysql", "postgresql", "postgres",
        "oracle", "sql server",
        "mongodb", "redis", "sqlite"
    },
    "data_engineering": {
        "data engineering", "etl", "elt",
        "spark", "pyspark",
        "hadoop", "hdfs",
        "airflow", "luigi",
        "kafka", "kinesis"
    },
    "devops": {
        "devops",
        "docker", "kubernetes", "k8s",
        "ci/cd", "jenkins", "github actions", "gitlab ci",
        "terraform", "ansible"
    },
    "frontend": {
        "javascript", "typescript",
        "react", "redux",
        "vue", "angular",
        "html", "css", "tailwind", "bootstrap"
    },
    "backend": {
        "node", "node.js", "express",
        "java", "spring", "spring boot",
        "go", "golang",
        "c#", ".net", "asp.net"
    },
    "analytics": {
        "excel", "power bi", "tableau",
        "lookerstudio", "looker",
        "google analytics"
    },
}

def normalize(text: str) -> str:
    return text.strip().lower()

def expand_skills(raw_skills):
    """
    raw_skills: list of strings from parsed resume
    returns: set of normalized skills + ontology expansions
    """
    if not raw_skills:
        return set()

    base = {normalize(s) for s in raw_skills if isinstance(s, str)}

    expanded = set(base)
    for canonical, synonyms in SKILL_ONTOLOGY.items():
        if canonical in base or any(s in base for s in synonyms):
            expanded.add(canonical)
            expanded.update(synonyms)

    return expanded
