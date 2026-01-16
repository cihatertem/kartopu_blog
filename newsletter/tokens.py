from django.core import signing


TOKEN_SALT = "newsletter"


def make_token(email: str, action: str) -> str:
    payload = {"email": email, "action": action}
    return signing.dumps(payload, salt=TOKEN_SALT)


def parse_token(token: str, max_age: int):
    return signing.loads(token, salt=TOKEN_SALT, max_age=max_age)
