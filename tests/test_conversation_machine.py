from vera.conversation.machine import ConversationMachine
from vera.domain.enums import ConversationStatus, Intent


def test_record_outbound_tracks_message_and_trigger():
    state = ConversationMachine.new("conv-1", "m-1")

    updated = ConversationMachine.record_outbound(state, "Hello", "t-1", "2026-04-26T10:00:00Z", 1)

    assert updated.status == ConversationStatus.WAITING_FOR_MERCHANT
    assert updated.sent_trigger_ids == ("t-1",)
    assert updated.messages[0].from_role == "vera"
    assert updated.pending_action == "await_reply"


def test_stop_reply_suppresses_conversation():
    state = ConversationMachine.new("conv-1", "m-1")

    updated = ConversationMachine.receive_reply(state, "Please stop", "2026-04-26T10:01:00Z", 2)

    assert updated.current_intent == Intent.STOP
    assert updated.status == ConversationStatus.SUPPRESSED
    assert "opt_out" in updated.merchant_signals
    assert updated.pending_action is None


def test_commitment_reply_moves_to_action_ready():
    state = ConversationMachine.new("conv-1", "m-1")

    updated = ConversationMachine.receive_reply(state, "Yes please, go ahead", "2026-04-26T10:01:00Z", 2)

    assert updated.current_intent == Intent.COMMITMENT
    assert updated.status == ConversationStatus.ACTION_READY
    assert updated.pending_action == "execute_committed_action"


def test_defer_reply_backs_off():
    state = ConversationMachine.new("conv-1", "m-1")

    updated = ConversationMachine.receive_reply(state, "Call me tomorrow", "2026-04-26T10:01:00Z", 2)

    assert updated.current_intent == Intent.DEFER
    assert updated.status == ConversationStatus.WAITING_FOR_MERCHANT
    assert updated.pending_action == "backoff"


def test_repeated_auto_reply_completes_after_third_identical_reply():
    state = ConversationMachine.new("conv-1", "m-1")
    body = "Thank you for contacting us. Team will respond."

    state = ConversationMachine.receive_reply(state, body, "2026-04-26T10:01:00Z", 1)
    state = ConversationMachine.receive_reply(state, body, "2026-04-26T10:02:00Z", 2)
    state = ConversationMachine.receive_reply(state, body, "2026-04-26T10:03:00Z", 3)

    assert state.current_intent == Intent.AUTO_REPLY
    assert state.status == ConversationStatus.COMPLETED
    assert state.merchant_signals == ("auto_reply",)
