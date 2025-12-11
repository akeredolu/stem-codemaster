# main/context_processors.py
def guest_chat_id(request):
    if request.user.is_authenticated:
        return {}  # real users already have username

    if 'guest_id' not in request.session:
        import uuid
        request.session['guest_id'] = f"guest_{uuid.uuid4().hex[:8]}"  

    return {"guest_id": request.session.get("guest_id")}

