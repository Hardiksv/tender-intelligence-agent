import os

content = (
    'import pytest\n'
    'from sqlalchemy import create_engine, event\n'
    'from sqlalchemy.orm import sessionmaker\n'
    'from app.db.database import Base\n'
    '\n'
    '\n'
    '@pytest.fixture(scope="session")\n'
    'def _test_engine():\n'
    '    engine = create_engine(\n'
    '        "sqlite:///./test_tmp.db",\n'
    '        connect_args={"check_same_thread": False},\n'
    '    )\n'
    '    Base.metadata.create_all(engine)\n'
    '    yield engine\n'
    '    Base.metadata.drop_all(engine)\n'
    '    engine.dispose()\n'
    '    try:\n'
    '        os.remove("test_tmp.db")\n'
    '    except Exception:\n'
    '        pass\n'
    '\n'
    '\n'
    '@pytest.fixture()\n'
    'def test_db(_test_engine):\n'
    '    connection = _test_engine.connect()\n'
    '    transaction = connection.begin()\n'
    '    TestSession = sessionmaker(bind=connection)\n'
    '    session = TestSession()\n'
    '    session.begin_nested()\n'
    '\n'
    '    @event.listens_for(session, "after_transaction_end")\n'
    '    def restart_savepoint(sess, trans):\n'
    '        if trans.nested and not trans._parent.nested:\n'
    '            sess.begin_nested()\n'
    '\n'
    '    yield session\n'
    '\n'
    '    session.close()\n'
    '    transaction.rollback()\n'
    '    connection.close()\n'
)

with open('backend/tests/conftest.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('conftest.py written, lines:', content.count('\n'))
