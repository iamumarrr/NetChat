from database.database import (
    initialize_database,
    hash_password,
    verify_password,
    register_user,
    authenticate_user
)


def test_password_hashing():

    password = "mySecret123"

    password_hash, salt = hash_password(
        password
    )

    print("Password hash:", password_hash)
    print("Salt:", salt)

    assert password_hash != password

    assert verify_password(
        password,
        password_hash,
        salt
    )

    assert not verify_password(
        "wrongPassword",
        password_hash,
        salt
    )

    print("✓ Password hashing test passed!")


def test_registration():

    initialize_database()

    username = "testuser"

    password = "testPassword123"

    success, message = register_user(
        username,
        password
    )

    print(message)

    if success:

        assert authenticate_user(
            username,
            password
        )

        assert not authenticate_user(
            username,
            "wrongPassword"
        )

        print(
            "✓ Registration and authentication test passed!"
        )


if __name__ == "__main__":

    test_password_hashing()

    test_registration()