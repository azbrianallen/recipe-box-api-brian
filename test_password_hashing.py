from security_utils import create_password_hash, verify_password

def main():
    plaintext = "TestPassword123!"  # demo only, not a real password
    stored_hash = create_password_hash(plaintext)

    print("STORED HASH:", stored_hash)
    print("correct? ", verify_password(stored_hash, "TestPassword123!"))
    print("wrong?   ", verify_password(stored_hash, "WrongPassword"))

if __name__ == "__main__":
    main()
    