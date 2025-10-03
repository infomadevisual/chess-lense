class Config():
    # Set debug to true does not interact with chesscom external API and loads only from cache
    debug :bool = False

    # loads a user's data on startup
    load_user:str | None = "joeshift"