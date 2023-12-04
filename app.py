import os
import chainlit as cl
from operator import itemgetter
from typing import Optional
from chainlit.client.base import ConversationDict
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import Runnable, RunnablePassthrough, RunnableLambda
from langchain.schema.runnable.config import RunnableConfig
from langchain.memory import ConversationBufferMemory


from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.runnable import Runnable
from langchain.schema.runnable.config import RunnableConfig

from prompt import PROMPT_WITH_SENTENCES
from auth import hash_password


def setup_runnable():
    memory = cl.user_session.get("memory")  # type: ConversationBufferMemory
    model = ChatOpenAI(model_name="gpt-4-1106-preview", streaming=True)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                PROMPT_WITH_SENTENCES,
            ),
            ("human", "{question}"),
        ]
    )

    runnable = (
        RunnablePassthrough.assign(
            history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
        )
        | prompt
        | model
        | StrOutputParser()
    )
    cl.user_session.set("runnable", runnable)




# TODO: Create a database to store hashed passwords
# Create a small endpoint to store user into a postgres database, Might use keycloak as a simple solution for that ?
# Create a docker compose to deploy all of that

@cl.password_auth_callback
def auth_callback(email: str, password: str) -> Optional[cl.AppUser]:
    # Retrieve the hashed password from the database
    hashed_password = hash_password(password)

    # Compare the input password with the hashed password
    # if bcrypt.checkpw(password.encode(), hashed_password.encode()):
    if email == os.getenv("ADMIN_EMAIL") and hashed_password == os.getenv("ADMIN_PASSWORD_HASH"):
        return cl.AppUser(username="admin", role="ADMIN", provider="credentials")
    else:
        return None


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("memory", ConversationBufferMemory(return_messages=True))
    setup_runnable()


@cl.on_chat_resume
async def on_chat_resume(conversation: ConversationDict):
    memory = ConversationBufferMemory(return_messages=True)
    root_messages = [m for m in conversation["messages"] if m["parentId"] == None]
    for message in root_messages:
        if message["authorIsUser"]:
            memory.chat_memory.add_user_message(message["content"])
        else:
            memory.chat_memory.add_ai_message(message["content"])

    cl.user_session.set("memory", memory)

    setup_runnable()


@cl.on_message
async def on_message(message: cl.Message):
    memory = cl.user_session.get("memory")  # type: ConversationBufferMemory

    runnable = cl.user_session.get("runnable")  # type: Runnable

    res = cl.Message(content="")

    async for chunk in runnable.astream(
        {"question": message.content},
        config=RunnableConfig(callbacks=[cl.LangchainCallbackHandler()]),
    ):
        await res.stream_token(chunk)

    await res.send()

    memory.chat_memory.add_user_message(message.content)
    memory.chat_memory.add_ai_message(res.content)
