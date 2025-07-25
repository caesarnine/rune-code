from __future__ import annotations

import pytest
import dataclasses

from rune.tools.todos import (
    AddTodosTodos,
    UpdateTodosUpdates,
    add_todos,
    list_todos,
    update_todos,

)


from rune.core.context import SessionContext



def test_add_todos_success(mock_run_context: RunContext[SessionContext]):
    result = add_todos(mock_run_context, [AddTodosTodos(title="test todo", note="a note", priority="high")])
    assert len(result.data["added_todos"]) == 1
    added = result.data["added_todos"][0]
    assert added["title"] == "test todo"
    assert added["note"] == "a note"
    assert added["priority"] == "high"
    assert added["status"] == "pending"
    assert len(mock_run_context.deps.todos) == 1


def test_list_todos_success(mock_run_context: RunContext[SessionContext]):
    add_todos(mock_run_context, [AddTodosTodos(title="t1"), AddTodosTodos(title="t2")])
    # Manually update the status of the second todo for the test
    todo_id = [t for t in mock_run_context.deps.todos if mock_run_context.deps.todos[t].title == 't2'][0]
    mock_run_context.deps.todos[todo_id].status = "completed"
    
    all_todos = list_todos(mock_run_context)
    assert len(all_todos.data["todos"]) == 2

    completed = list_todos(mock_run_context, status="completed")
    assert len(completed.data["todos"]) == 1
    assert completed.data["todos"][0]["title"] == "t2"

    pending_high = list_todos(mock_run_context, status="pending", priority="high")
    assert len(pending_high.data["todos"]) == 0


def test_update_todos_success(mock_run_context: RunContext[SessionContext]):
    add_result = add_todos(mock_run_context, [AddTodosTodos(title="test todo")])
    todo_id = add_result.data["added_todos"][0]["id"]

    update_result = update_todos(mock_run_context, [
        UpdateTodosUpdates(id=todo_id, status="completed", priority="medium", note="new note")
    ])
    updated = update_result.data["updated_todos"][0]
    assert updated["status"] == "completed"
    assert updated["priority"] == "medium"
    assert updated["note"] == "new note"

    assert mock_run_context.deps.todos[todo_id].status == "completed"


def test_update_todos_not_found(mock_run_context: RunContext[SessionContext]):
    with pytest.raises(ValueError, match="Todo with id .* not found"):
        update_todos(mock_run_context, [UpdateTodosUpdates(id="non-existent-id", status="completed")])
