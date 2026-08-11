import json
import random

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm

# Import Django's default User model
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count  # For counting questions (already imported)
from django.forms import inlineformset_factory
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    AnswerForm,
    CustomUserCreationForm,
    MatchingPairForm,
    QuestionForm,
    TestForm,
    UserAnswerForm,
    UserBlockForm,
)

# Import your custom UserProfile model and the forms
from .models import (
    Answer,
    MatchingPair,
    MatchingRight,
    Question,
    Test,
    TestAttempt,
    UserAnswer,
    UserProfile,
)

# --- Authentication Views ---


def signup_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)  # <--- USE CustomUserCreationForm
        if form.is_valid():
            user = form.save()
            # Log the user in after successful signup
            login(request, user)
            messages.success(
                request, f"Welcome, {user.username}! Your account has been created."
            )
            return redirect("test_list")  # Redirect to tests page or landing
    else:
        form = CustomUserCreationForm()  # <--- USE CustomUserCreationForm
    return render(request, "registration/signup.html", {"form": form})


# Django's built-in login/logout views via accounts/ urls are used automatically.
# Their templates are expected in registration/login.html and registration/logged_out.html


# --- General Views ---


def landing_page(request):
    from django.db.models import Count
    from quiz.models import Test, Question

    categories = Test.objects.annotate(q_count=Count("questions")).order_by("position", "name")
    total_questions = Question.objects.count()
    total_categories = Test.objects.count()

    context = {
        "categories": categories,
        "total_questions": total_questions,
        "total_categories": total_categories,
    }
    return render(request, "quiz/landing_page.html", context)


def study_view(request):
    return render(request, "quiz/study.html")


def about_view(request):
    return render(request, "quiz/about.html")


@login_required
def test_list(request):
    # --- MODIFIED: Annotate tests with question_count and order by position ---
    tests = Test.objects.annotate(question_count=Count("questions")).order_by(
        "position", "name"
    )
    # --- END MODIFIED ---
    return render(request, "quiz/test_list.html", {"tests": tests})


# --- Quiz Taking Views ---


@login_required
def start_test(request, test_id):
    # Check if user is blocked via their UserProfile
    if (
        request.user.userprofile.blocked_until
        and request.user.userprofile.blocked_until > timezone.now()
    ):
        messages.error(
            request,
            "You are temporarily blocked from taking tests until "
            + request.user.userprofile.blocked_until.strftime("%Y-%m-%d %H:%M"),
        )
        return redirect("test_list")  # Redirect back to test list or home

    test = get_object_or_404(Test, id=test_id)

    # Create a new test attempt
    attempt = TestAttempt.objects.create(user=request.user, test=test)

    # Get all questions for this test and shuffle them
    questions = list(test.questions.all())
    random.shuffle(questions)
    # Store shuffled order in session so it stays consistent
    request.session[f"attempt_{attempt.id}_order"] = [q.id for q in questions]

    # Redirect to the first question (index 0)
    return redirect(reverse("take_question", args=[attempt.id, 0]))


@login_required
def take_question(request, attempt_id, question_index):
    # Check if user is blocked via their UserProfile
    if (
        request.user.userprofile.blocked_until
        and request.user.userprofile.blocked_until > timezone.now()
    ):
        messages.error(
            request,
            "You are temporarily blocked from taking tests until "
            + request.user.userprofile.blocked_until.strftime("%Y-%m-%d %H:%M"),
        )
        return redirect("test_list")

    attempt = get_object_or_404(
        TestAttempt, id=attempt_id, user=request.user, completed=False
    )
    test = attempt.test

    # Load questions in the stored shuffled order from session
    order = request.session.get(f"attempt_{attempt.id}_order")
    if order:
        questions = list(Question.objects.filter(id__in=order))
        questions = sorted(questions, key=lambda q: order.index(q.id))
    else:
        questions = list(test.questions.all())
        random.shuffle(questions)
        request.session[f"attempt_{attempt.id}_order"] = [q.id for q in questions]

    total_questions = len(questions)

    if question_index >= total_questions:
        return redirect(reverse("finish_test", args=[attempt.id]))

    current_question = questions[question_index]

    # Check if user has already answered this question
    existing_user_answer = UserAnswer.objects.filter(
        test_attempt=attempt, question=current_question
    ).first()

    # ========== MULTIPLE CHOICE BRANCH ==========
    if current_question.is_multiple_choice:
        answers = current_question.answers.all()

        if request.method == "POST":
            form = UserAnswerForm(request.POST, question=current_question)
            if form.is_valid():
                selected_answer_objects = form.cleaned_data["selected_answers"]
                selected_answer_ids = [a.id for a in selected_answer_objects]

                with transaction.atomic():
                    if existing_user_answer:
                        existing_user_answer.selected_answers.clear()
                        existing_user_answer.delete()

                    user_answer = UserAnswer.objects.create(
                        test_attempt=attempt,
                        question=current_question,
                        is_correct=False,
                    )
                    user_answer.selected_answers.set(selected_answer_objects)

                    if test.test_type == "learning":
                        correct_answer_ids = set(
                            Answer.objects.filter(
                                question=current_question, is_correct=True
                            ).values_list("id", flat=True)
                        )
                        is_correct = correct_answer_ids == set(selected_answer_ids)
                        user_answer.is_correct = is_correct
                        user_answer.save()

                        context = {
                            "attempt": attempt,
                            "question": current_question,
                            "answers": answers,
                            "form": form,
                            "question_index": question_index,
                            "total_questions": total_questions,
                            "is_learning_mode": True,
                            "user_submitted": True,
                            "user_answer_object": user_answer,
                            "is_user_correct": is_correct,
                            "correct_answers": Answer.objects.filter(
                                question=current_question, is_correct=True
                            ),
                        }
                        return render(request, "quiz/take_question.html", context)

                    elif test.test_type == "exam":
                        return redirect(
                            reverse(
                                "take_question",
                                args=[attempt.id, question_index + 1],
                            )
                        )
            else:
                context = {
                    "attempt": attempt,
                    "question": current_question,
                    "answers": answers,
                    "form": form,
                    "question_index": question_index,
                    "total_questions": total_questions,
                    "is_learning_mode": test.test_type == "learning",
                    "user_submitted": False,
                }
                return render(request, "quiz/take_question.html", context)

        else:  # GET
            form = UserAnswerForm(question=current_question)
            context = {
                "attempt": attempt,
                "question": current_question,
                "answers": answers,
                "form": form,
                "question_index": question_index,
                "total_questions": total_questions,
                "is_learning_mode": test.test_type == "learning",
                "user_submitted": False,
            }
            return render(request, "quiz/take_question.html", context)

    # ========== MATCHING BRANCH ==========
    else:
        matching_pairs = list(current_question.matching_pairs.all())
        left_items = [{"id": p.id, "text": p.left_text} for p in matching_pairs]
        # Pool items: all right texts from each pair
        pool_items = []
        for p in matching_pairs:
            for text in p.get_all_rights():
                pool_items.append(
                    {"id": len(pool_items), "pair_id": p.id, "text": text}
                )
        shuffled_pool = pool_items.copy()
        random.shuffle(shuffled_pool)

        if request.method == "POST":
            categories_json = request.POST.get("categories_data", "{}")
            try:
                categories_data = json.loads(categories_json)
            except json.JSONDecodeError:
                categories_data = {}

            # Build mapping: use unique item id, store text+pair_id+cat_id
            user_mapping = {}
            for cat_id_str, items in categories_data.items():
                cat_id = int(cat_id_str)
                for item in items:
                    unique_id = str(item.get("id"))
                    user_mapping[unique_id] = {
                        "cat_id": cat_id,
                        "pair_id": item.get("pair_id", item.get("id")),
                        "text": item.get("text", ""),
                    }

            with transaction.atomic():
                if existing_user_answer:
                    existing_user_answer.delete()

                user_answer = UserAnswer.objects.create(
                    test_attempt=attempt,
                    question=current_question,
                    is_correct=False,
                    matching_answer=user_mapping,
                )

                if test.test_type == "learning":
                    correct_mapping = {str(p.id): p.id for p in matching_pairs}
                    # Check: each item's pair_id == placed category_id
                    all_items_correct = True
                    for placement in user_mapping.values():
                        if placement["pair_id"] != placement["cat_id"]:
                            all_items_correct = False
                    is_correct = all_items_correct and len(user_mapping) > 0
                    user_answer.is_correct = is_correct
                    user_answer.save()

                    pair_results = []
                    for pair in matching_pairs:
                        user_matched_id = None
                        for placement in user_mapping.values():
                            if placement["cat_id"] == pair.id:
                                user_matched_id = placement["pair_id"]
                                break
                        pair_results.append(
                            {
                                "pair": pair,
                                "is_correct": user_matched_id == pair.id,
                            }
                        )

                    context = {
                        "attempt": attempt,
                        "question": current_question,
                        "question_index": question_index,
                        "total_questions": total_questions,
                        "is_learning_mode": True,
                        "is_matching": True,
                        "matching_pairs": matching_pairs,
                        "left_items": left_items,
                        "shuffled_pool": shuffled_pool,
                        "user_submitted": True,
                        "is_user_correct": is_correct,
                        "pair_results": pair_results,
                    }
                    return render(request, "quiz/take_question.html", context)

                elif test.test_type == "exam":
                    return redirect(
                        reverse("take_question", args=[attempt.id, question_index + 1])
                    )

        else:  # GET
            context = {
                "attempt": attempt,
                "question": current_question,
                "question_index": question_index,
                "total_questions": total_questions,
                "is_learning_mode": test.test_type == "learning",
                "is_matching": True,
                "matching_pairs": matching_pairs,
                "left_items": left_items,
                "shuffled_pool": shuffled_pool,
                "user_submitted": False,
            }
            return render(request, "quiz/take_question.html", context)


@login_required
def finish_test(request, attempt_id):
    attempt = get_object_or_404(
        TestAttempt, id=attempt_id, user=request.user, completed=False
    )
    test = attempt.test
    questions = list(test.questions.all())
    total_questions = len(questions)
    correct_count = 0

    if test.test_type == "exam":
        for question in questions:
            try:
                user_answer = UserAnswer.objects.get(
                    test_attempt=attempt, question=question
                )

                # ----- Multiple Choice Scoring -----
                if question.is_multiple_choice:
                    correct_answers = set(
                        Answer.objects.filter(
                            question=question, is_correct=True
                        ).values_list("id", flat=True)
                    )
                    user_selected_answers = set(
                        user_answer.selected_answers.values_list("id", flat=True)
                    )
                    is_correct = correct_answers == user_selected_answers

                # ----- Matching Scoring -----
                else:
                    user_mapping = user_answer.matching_answer or {}
                    all_items_correct = True
                    for placement in user_mapping.values():
                        if isinstance(placement, dict):
                            if placement.get("pair_id") != placement.get("cat_id"):
                                all_items_correct = False
                        else:
                            # Legacy format: {pair_id: cat_id}
                            all_items_correct = False
                    is_correct = all_items_correct and len(user_mapping) > 0

                user_answer.is_correct = is_correct
                user_answer.save()

                if is_correct:
                    correct_count += 1

            except UserAnswer.DoesNotExist:
                pass

        if total_questions > 0:
            score = (correct_count / total_questions) * 100
        else:
            score = 0.0

        attempt.score = round(score, 2)

    attempt.end_time = timezone.now()
    attempt.completed = True
    attempt.save()

    return redirect(reverse("test_results", args=[attempt.id]))


@login_required
def test_results(request, attempt_id):
    attempt = get_object_or_404(
        TestAttempt, id=attempt_id, user=request.user, completed=True
    )
    test = attempt.test
    user_answers = (
        attempt.user_answers.all()
        .select_related("question")
        .prefetch_related(
            "selected_answers", "question__answers", "question__matching_pairs"
        )
    )

    results_data = []
    for ua in user_answers:
        question = ua.question

        if question.is_multiple_choice:
            correct_answers = Answer.objects.filter(question=question, is_correct=True)
            selected_answers = ua.selected_answers.all()
            correct_ids = set(correct_answers.values_list("id", flat=True))
            selected_ids = set(selected_answers.values_list("id", flat=True))
            is_correct_for_display = correct_ids == selected_ids
            results_data.append(
                {
                    "question": question,
                    "user_selected_answers": selected_answers,
                    "correct_answers": correct_answers,
                    "is_user_correct": is_correct_for_display,
                    "is_matching": False,
                }
            )
        else:
            matching_pairs = question.matching_pairs.all()
            user_mapping = ua.matching_answer or {}
            cat_results = []
            all_correct = True
            for pair in matching_pairs:
                correct_texts = pair.get_all_rights()
                placed_items = []
                for unique_id, placement in user_mapping.items():
                    if isinstance(placement, dict):
                        cat_id = placement.get("cat_id")
                        item_pair_id = placement.get("pair_id")
                        item_text = placement.get("text", "")
                    else:
                        item_pair_id = int(unique_id)
                        cat_id = placement
                        item_text = ""
                    if cat_id == pair.id:
                        belongs_to = ""
                        if item_pair_id:
                            src = next(
                                (p for p in matching_pairs if p.id == item_pair_id),
                                None,
                            )
                            belongs_to = src.left_text if src else ""
                        placed_items.append(
                            {
                                "text": item_text,
                                "belongs_to": belongs_to,
                                "is_correct": item_pair_id == pair.id,
                            }
                        )
                for ct in correct_texts:
                    if not any(
                        pi["text"] == ct and pi["is_correct"] for pi in placed_items
                    ):
                        all_correct = False
                cat_results.append(
                    {
                        "pair": pair,
                        "correct_texts": correct_texts,
                        "placed_items": placed_items,
                        "is_fully_correct": len(placed_items) == len(correct_texts)
                        and all(pi["is_correct"] for pi in placed_items),
                    }
                )
            results_data.append(
                {
                    "question": question,
                    "is_user_correct": all_correct,
                    "is_matching": True,
                    "cat_results": cat_results,
                }
            )

    context = {
        "attempt": attempt,
        "test": test,
        "results_data": results_data,
        "is_learning_mode": test.test_type == "learning",
    }
    return render(request, "quiz/test_results.html", context)


# ============================================================
# PRACTICE EXAM VIEWS (Session-based, NOT saved to database)
# ============================================================

QUESTION_COUNT_CHOICES = [50, 70, 90, 100]

# Time limit mapping: question count -> minutes
QUESTION_TIME_MAP = {
    50: 60,
    70: 90,
    90: 120,
    100: 120,
}


def _get_time_limit(num_questions):
    """Get time limit in minutes based on number of questions."""
    if num_questions in QUESTION_TIME_MAP:
        return QUESTION_TIME_MAP[num_questions]
    # Custom: 1.5 min per question, min 2, max 180
    return max(2, min(180, num_questions * 1.5))


@login_required
def practice_exam(request):
    """Show the practice exam generator form."""
    tests = Test.objects.annotate(q_count=Count("questions")).filter(q_count__gt=0)

    context = {
        "tests": tests,
        "question_counts": QUESTION_COUNT_CHOICES,
    }
    return render(request, "quiz/practice_exam.html", context)


@login_required
def practice_start(request):
    """Generate a random practice exam and store question IDs in session."""
    if request.method != "POST":
        return redirect("practice_exam")

    # --- Parse form inputs ---
    selected_test_ids = request.POST.getlist("sections")
    question_count_str = request.POST.get("question_count", "")
    custom_count_str = request.POST.get("custom_count", "")

    # Determine question count
    if question_count_str == "custom":
        try:
            num_questions = int(custom_count_str)
        except (ValueError, TypeError):
            messages.error(request, "Please enter a valid number for custom question count.")
            return redirect("practice_exam")
    else:
        try:
            num_questions = int(question_count_str)
        except (ValueError, TypeError):
            messages.error(request, "Please select a question count.")
            return redirect("practice_exam")

    if num_questions < 1:
        messages.error(request, "Number of questions must be at least 1.")
        return redirect("practice_exam")

    # Validate sections
    if not selected_test_ids:
        messages.error(request, "Please select at least one section.")
        return redirect("practice_exam")

    # Get selected tests
    selected_tests = Test.objects.filter(id__in=selected_test_ids).annotate(
        q_count=Count("questions")
    )

    if not selected_tests:
        messages.error(request, "No valid sections selected.")
        return redirect("practice_exam")

    # Check total available questions
    total_available = sum(t.q_count for t in selected_tests)
    if num_questions > total_available:
        messages.error(
            request,
            f"Only {total_available} questions are available in the selected sections. "
            f"Please reduce the number of questions or choose more sections.",
        )
        return redirect("practice_exam")

    # --- Proportional distribution ---
    questions_by_test = {}
    remaining = num_questions

    test_list = list(selected_tests)
    for i, test in enumerate(test_list):
        if i == len(test_list) - 1:
            # Last test gets all remaining
            count = remaining
        else:
            # Proportional: round down
            count = max(1, int(num_questions * test.q_count / total_available))
            count = min(count, test.q_count, remaining)
        questions_by_test[test.id] = count
        remaining -= count

    # --- Select random questions ---
    all_question_ids = []
    selected_names = []

    for test in test_list:
        count = questions_by_test[test.id]
        qs = list(
            Question.objects.filter(test=test)
            .values_list("id", flat=True)
            .order_by("?")[:count]
        )
        all_question_ids.extend(qs)
        selected_names.append(test.name)

    # Shuffle all selected questions
    random.shuffle(all_question_ids)

    # Calculate time limit
    time_limit_minutes = _get_time_limit(num_questions)
    from datetime import datetime

    # --- Store in session ---
    practice_data = {
        "question_ids": all_question_ids,
        "answers": {},  # {str(question_id): answer_data}
        "total_questions": len(all_question_ids),
        "selected_sections": selected_names,
        "time_limit_minutes": time_limit_minutes,
        "started_at": datetime.now().isoformat(),
    }
    request.session["practice_exam"] = practice_data

    return redirect(reverse("practice_take", args=[0]))


@login_required
def practice_take(request, question_index):
    """Display a practice exam question (reuses take_question.html)."""
    practice_data = request.session.get("practice_exam")
    if not practice_data:
        messages.error(request, "No active practice exam. Please start a new one.")
        return redirect("practice_exam")

    question_ids = practice_data["question_ids"]
    total_questions = len(question_ids)

    if question_index >= total_questions:
        return redirect("practice_finish")

    current_question = get_object_or_404(Question, id=question_ids[question_index])
    answers_dict = practice_data.get("answers", {})
    existing_answer = answers_dict.get(str(current_question.id))

    # Context for take_question.html
    context = {
        "question": current_question,
        "question_index": question_index,
        "total_questions": total_questions,
        "is_matching": current_question.is_matching,
        "is_practice": True,
        "practice_index": question_index,
        "is_learning_mode": False,
        "user_submitted": existing_answer is not None,
        "time_limit_minutes": practice_data.get("time_limit_minutes", 60),
        "started_at": practice_data.get("started_at", ""),
    }

    # Check if time expired
    from datetime import datetime
    started_at_str = practice_data.get("started_at", "")
    time_limit = practice_data.get("time_limit_minutes", 60)
    if started_at_str:
        started = datetime.fromisoformat(started_at_str)
        elapsed = (datetime.now() - started).total_seconds()
        if elapsed >= time_limit * 60:
            # Time's up — redirect to finish
            return redirect("practice_finish")

    if existing_answer is not None:
        # Already answered - show result
        if current_question.is_multiple_choice:
            selected_ids = existing_answer.get("selected_ids", [])
            correct_ids = set(
                Answer.objects.filter(
                    question=current_question, is_correct=True
                ).values_list("id", flat=True)
            )
            is_correct = set(selected_ids) == correct_ids
            context["is_user_correct"] = is_correct
            context["correct_answers"] = Answer.objects.filter(
                question=current_question, is_correct=True
            )
        else:
            # Matching: build pair_results
            matching_pairs = current_question.matching_pairs.all()
            user_mapping = existing_answer.get("mapping", {})
            pair_results = []
            all_correct_flag = True
            for pair in matching_pairs:
                cat_id = str(pair.id)
                placed = user_mapping.get(cat_id, [])
                # Check if all correct texts match
                correct_texts = pair.get_all_rights()
                placed_texts = [p.get("text", "") for p in placed]
                is_pair_correct = sorted(placed_texts) == sorted(correct_texts)
                if not is_pair_correct:
                    all_correct_flag = False
                pair_results.append({
                    "pair": pair,
                    "is_correct": is_pair_correct,
                })
            context["pair_results"] = pair_results
            context["is_user_correct"] = all_correct_flag

        return render(request, "quiz/take_question.html", context)

    # --- Handle POST (submit answer) ---
    if request.method == "POST":
        if current_question.is_multiple_choice:
            form = UserAnswerForm(request.POST, question=current_question)
            if form.is_valid():
                selected = form.cleaned_data["selected_answers"]
                selected_ids = [a.id for a in selected]
                answers_dict[str(current_question.id)] = {"selected_ids": selected_ids}
                practice_data["answers"] = answers_dict
                request.session["practice_exam"] = practice_data

                # Redirect to next question or results
                next_idx = question_index + 1
                if next_idx < total_questions:
                    return redirect(reverse("practice_take", args=[next_idx]))
                else:
                    return redirect("practice_finish")
        else:
            # Matching submission
            categories_json = request.POST.get("categories_data", "{}")
            try:
                matching_data = json.loads(categories_json)
            except json.JSONDecodeError:
                matching_data = {}

            answers_dict[str(current_question.id)] = {"mapping": matching_data}
            practice_data["answers"] = answers_dict
            request.session["practice_exam"] = practice_data

            next_idx = question_index + 1
            if next_idx < total_questions:
                return redirect(reverse("practice_take", args=[next_idx]))
            else:
                return redirect("practice_finish")

    # --- GET: show question form ---
    if current_question.is_multiple_choice:
        context["form"] = UserAnswerForm(question=current_question)
    else:
        # Matching: build left_items and shuffled_pool
        matching_pairs = current_question.matching_pairs.all()
        left_items = [{"id": p.id, "text": p.left_text} for p in matching_pairs]

        pool_items = []
        item_id = 0
        for pair in matching_pairs:
            for right_text in pair.get_all_rights():
                item_id += 1
                pool_items.append({
                    "id": item_id,
                    "pair_id": pair.id,
                    "text": right_text,
                })
        random.shuffle(pool_items)

        context["left_items"] = left_items
        context["shuffled_pool"] = pool_items

    return render(request, "quiz/take_question.html", context)


@login_required
def practice_finish(request):
    """Score the practice exam and show results."""
    practice_data = request.session.get("practice_exam")
    if not practice_data:
        messages.error(request, "No active practice exam.")
        return redirect("practice_exam")

    question_ids = practice_data["question_ids"]
    answers_dict = practice_data.get("answers", {})

    results_data = []
    correct_count = 0

    for qid in question_ids:
        question = get_object_or_404(Question, id=qid)
        answer_data = answers_dict.get(str(qid))

        if question.is_multiple_choice:
            correct_answers = Answer.objects.filter(question=question, is_correct=True)
            correct_ids = set(correct_answers.values_list("id", flat=True))

            if answer_data:
                selected_ids = set(answer_data.get("selected_ids", []))
                is_correct = selected_ids == correct_ids
                selected_answers = Answer.objects.filter(id__in=selected_ids)
            else:
                is_correct = False
                selected_answers = Answer.objects.none()

            results_data.append({
                "question": question,
                "user_selected_answers": selected_answers,
                "correct_answers": correct_answers,
                "is_user_correct": is_correct,
                "is_matching": False,
            })

            if is_correct:
                correct_count += 1

        else:
            # Matching
            matching_pairs = question.matching_pairs.all()
            user_mapping = answer_data.get("mapping", {}) if answer_data else {}
            cat_results = []
            all_correct = True

            for pair in matching_pairs:
                correct_texts = pair.get_all_rights()
                placed_items = []
                for unique_id, placement in user_mapping.items():
                    if isinstance(placement, dict):
                        cat_id = placement.get("cat_id")
                        item_pair_id = placement.get("pair_id")
                        item_text = placement.get("text", "")
                    else:
                        item_pair_id = int(unique_id)
                        cat_id = placement
                        item_text = ""
                    if cat_id == pair.id:
                        belongs_to = ""
                        if item_pair_id:
                            src = next(
                                (p for p in matching_pairs if p.id == item_pair_id),
                                None,
                            )
                            belongs_to = src.left_text if src else ""
                        placed_items.append({
                            "text": item_text,
                            "belongs_to": belongs_to,
                            "is_correct": item_pair_id == pair.id,
                        })
                for ct in correct_texts:
                    if not any(
                        pi["text"] == ct and pi["is_correct"] for pi in placed_items
                    ):
                        all_correct = False
                cat_results.append({
                    "pair": pair,
                    "correct_texts": correct_texts,
                    "placed_items": placed_items,
                    "is_fully_correct": len(placed_items) == len(correct_texts)
                    and all(pi["is_correct"] for pi in placed_items),
                })

            if all_correct:
                correct_count += 1

            results_data.append({
                "question": question,
                "is_user_correct": all_correct,
                "is_matching": True,
                "cat_results": cat_results,
            })

    total = len(question_ids)
    score = round((correct_count / total) * 100, 2) if total > 0 else 0.0
    wrong_count = total - correct_count

    # --- Per-section stats ---
    from datetime import datetime
    from collections import OrderedDict

    section_data = OrderedDict()
    for qid in question_ids:
        question = Question.objects.select_related("test").get(id=qid)
        section_name = question.test.name if question.test else "Unknown"
        if section_name not in section_data:
            section_data[section_name] = {"total": 0, "correct": 0, "wrong": 0}
        section_data[section_name]["total"] += 1
        answer_data = answers_dict.get(str(qid))
        if question.is_multiple_choice:
            if answer_data:
                correct_ids = set(
                    Answer.objects.filter(question=question, is_correct=True).values_list("id", flat=True)
                )
                selected_ids = set(answer_data.get("selected_ids", []))
                if selected_ids == correct_ids:
                    section_data[section_name]["correct"] += 1
                else:
                    section_data[section_name]["wrong"] += 1
            else:
                section_data[section_name]["wrong"] += 1
        else:
            if answer_data:
                user_mapping = answer_data.get("mapping", {})
                matching_pairs = question.matching_pairs.all()
                is_correct = True
                for pair in matching_pairs:
                    correct_texts = set(pair.get_all_rights())
                    cat_id = str(pair.id)
                    placed = user_mapping.get(cat_id, [])
                    placed_texts = set(p.get("text", "") for p in placed)
                    if placed_texts != correct_texts:
                        is_correct = False
                        break
                if is_correct:
                    section_data[section_name]["correct"] += 1
                else:
                    section_data[section_name]["wrong"] += 1
            else:
                section_data[section_name]["wrong"] += 1

    def get_rating(acc):
        if acc >= 90: return ("Excellent", "success")
        if acc >= 80: return ("Very Good", "info")
        if acc >= 70: return ("Good", "primary")
        if acc >= 60: return ("Fair", "warning")
        return ("Needs Improvement", "error")

    section_stats = []
    for name, stats in section_data.items():
        acc = round((stats["correct"] / stats["total"]) * 100, 1) if stats["total"] > 0 else 0
        rating, rating_color = get_rating(acc)
        section_stats.append({
            "name": name,
            "total": stats["total"],
            "correct": stats["correct"],
            "wrong": stats["wrong"],
            "accuracy": acc,
            "rating": rating,
            "rating_color": rating_color,
        })

    # --- Time used ---
    started_at_str = practice_data.get("started_at", "")
    time_used_minutes = 0
    if started_at_str:
        started = datetime.fromisoformat(started_at_str)
        elapsed = (datetime.now() - started).total_seconds()
        time_used_minutes = round(elapsed / 60, 1)

    # --- Weakest sections ---
    sorted_sections = sorted(section_stats, key=lambda s: s["accuracy"])
    weakest_sections = sorted_sections[:2] if len(sorted_sections) >= 2 else sorted_sections

    context = {
        "results_data": results_data,
        "total_questions": total,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "score": score,
        "is_practice": True,
        "selected_sections": practice_data.get("selected_sections", []),
        "section_stats": section_stats,
        "time_used_minutes": time_used_minutes,
        "weakest_sections": weakest_sections,
    }

    return render(request, "quiz/practice_results.html", context)


# --- Custom Admin Views ---


# Helper to check if user is staff (can be improved with custom group checks)
def is_staff_check(user):
    return user.is_staff


@login_required
@user_passes_test(is_staff_check)
def reorder_tests(request):
    """Handle test reordering via AJAX"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            test_ids = data.get("test_ids", [])

            # Update positions for each test
            for index, test_id in enumerate(test_ids):
                Test.objects.filter(id=test_id).update(position=index)

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


# --- MODIFIED: custom_admin_questions to handle optional test_id ---
@user_passes_test(is_staff_check)
def custom_admin_questions(
    request, test_id=None
):  # <--- Added optional test_id parameter
    questions_queryset = (
        Question.objects.all().select_related("test").prefetch_related("answers")
    )
    test_obj = None  # Initialize test_obj to None

    if test_id:
        test_obj = get_object_or_404(Test, id=test_id)
        questions_queryset = questions_queryset.filter(
            test=test_obj
        )  # Filter by the specific test

    context = {
        "questions": questions_queryset,
        "test_obj": test_obj,  # Pass the Test object to the template
    }
    return render(request, "quiz/custom_admin/questions_list.html", context)


# --- Backup / Export / Import ---
@user_passes_test(is_staff_check)
def export_questions(request):
    from django.core.serializers.json import DjangoJSONEncoder
    from datetime import datetime

    questions = Question.objects.all().prefetch_related("answers", "matching_pairs__extra_rights")

    data = {
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        "total_questions": questions.count(),
        "questions": [],
    }

    for q in questions:
        q_data = {
            "text": q.text,
            "question_type": q.question_type,
            "test_name": q.test.name if q.test else "",
        }

        if q.is_multiple_choice:
            q_data["answers"] = [
                {"text": a.text, "is_correct": a.is_correct}
                for a in q.answers.all()
            ]
            q_data["matching_pairs"] = []
        else:
            q_data["answers"] = []
            q_data["matching_pairs"] = []
            for pair in q.matching_pairs.all():
                q_data["matching_pairs"].append({
                    "left_text": pair.left_text,
                    "right_text": pair.right_text,
                    "extra_rights": [er.text for er in pair.extra_rights.all()],
                })

        data["questions"].append(q_data)

    response = JsonResponse(data, json_dumps_params={"indent": 2, "ensure_ascii": False})
    response["Content-Disposition"] = 'attachment; filename="questions_backup.json"'
    return response


@user_passes_test(is_staff_check)
def import_questions(request):
    if request.method == "POST":
        import_file = request.FILES.get("import_file")
        if not import_file:
            messages.error(request, "Please select a backup file to import.")
            return redirect("custom_admin_questions")

        try:
            data = json.loads(import_file.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            messages.error(request, "Invalid file. Please upload a valid JSON backup file.")
            return redirect("custom_admin_questions")

        if "questions" not in data:
            messages.error(request, "Invalid backup format: missing 'questions' key.")
            return redirect("custom_admin_questions")

        created_count = 0
        skipped_count = 0

        for q_data in data["questions"]:
            text = q_data.get("text", "").strip()
            if not text:
                skipped_count += 1
                continue

            question_type = q_data.get("question_type", "mc")
            test_name = q_data.get("test_name", "")

            # Find or create test
            test = None
            if test_name:
                test, _ = Test.objects.get_or_create(
                    name__iexact=test_name,
                    defaults={"name": test_name, "test_type": "exam"},
                )

            with transaction.atomic():
                question = Question.objects.create(
                    text=text,
                    question_type=question_type,
                    test=test,
                )

                if question_type == "mc":
                    for a_data in q_data.get("answers", []):
                        Answer.objects.create(
                            question=question,
                            text=a_data.get("text", ""),
                            is_correct=a_data.get("is_correct", False),
                        )
                else:
                    for mp_data in q_data.get("matching_pairs", []):
                        pair = MatchingPair.objects.create(
                            question=question,
                            left_text=mp_data.get("left_text", ""),
                            right_text=mp_data.get("right_text", ""),
                        )
                        for er_text in mp_data.get("extra_rights", []):
                            MatchingRight.objects.create(
                                pair=pair,
                                text=er_text,
                            )

            created_count += 1

        messages.success(
            request,
            f"Import complete: {created_count} questions created, {skipped_count} skipped.",
        )
        return redirect("custom_admin_questions")

    messages.error(request, "Invalid request method.")
    return redirect("custom_admin_questions")


# Use inline formset to manage answers along with the question
AnswerInlineFormSet = inlineformset_factory(
    Question, Answer, form=AnswerForm, extra=4, can_delete=True
)

# Use inline formset to manage matching pairs along with the question
MatchingPairInlineFormSet = inlineformset_factory(
    Question, MatchingPair, form=MatchingPairForm, extra=2, can_delete=True
)


def _save_matching_rights(question, request):
    """Save extra right answers from rights_json"""
    pairs = MatchingPair.objects.filter(question=question)
    all_rights = request.POST.getlist("matching_pairs-rights_json")
    for idx, pair in enumerate(pairs):
        pair.extra_rights.all().delete()
        if idx < len(all_rights):
            try:
                rights = json.loads(all_rights[idx])
            except (json.JSONDecodeError, TypeError):
                rights = []
            for text in rights:
                if text.strip():
                    MatchingRight.objects.create(pair=pair, text=text.strip())


# --- MODIFIED: custom_admin_add_question to handle optional test_id ---
@user_passes_test(is_staff_check)
def custom_admin_add_question(
    request, test_id=None
):  # <--- Added optional test_id parameter
    test_obj = None
    initial_data = {}

    if test_id:
        test_obj = get_object_or_404(Test, id=test_id)
        initial_data["test"] = test_obj

    if request.method == "POST":
        form = QuestionForm(request.POST, request.FILES)
        question_type = request.POST.get("question_type", "mc")

        if question_type == "mc":
            formset = AnswerInlineFormSet(request.POST, request.FILES)
            matching_formset = MatchingPairInlineFormSet()  # dummy, not used
        else:
            formset = AnswerInlineFormSet()  # dummy, not used
            matching_formset = MatchingPairInlineFormSet(request.POST, request.FILES)

        if question_type == "mc":
            if form.is_valid() and formset.is_valid():
                question = form.save(commit=False)
                if test_obj:
                    question.test = test_obj

                answers_data = formset.cleaned_data
                has_correct_answer = any(
                    answer.get("is_correct")
                    for answer in answers_data
                    if not answer.get("DELETE")
                )

                if has_correct_answer:
                    valid_answers_count = sum(
                        1 for f in formset if not f.cleaned_data.get("DELETE")
                    )
                    if valid_answers_count >= 2:
                        question.save()
                        formset.instance = question
                        formset.save()
                        if test_obj:
                            messages.success(
                                request,
                                "Question added successfully to " + test_obj.name + ".",
                            )
                            return redirect(
                                reverse(
                                    "custom_admin_test_questions", args=[test_obj.id]
                                )
                            )
                        else:
                            messages.success(request, "Question added successfully.")
                            next_url = request.POST.get("next") or request.GET.get(
                                "next"
                            )
                            if next_url:
                                return redirect(next_url)
                            return redirect("custom_admin_questions")
                    else:
                        form.add_error(None, "Please provide at least 2 answers.")
                else:
                    form.add_error(None, "Please mark at least one answer as correct.")
            else:
                if not form.is_valid():
                    messages.error(
                        request, "Please correct the errors in the question form."
                    )
                if not formset.is_valid():
                    messages.error(request, "Please correct the errors in the answers.")
        else:
            # Matching question
            if form.is_valid() and matching_formset.is_valid():
                question = form.save(commit=False)
                if test_obj:
                    question.test = test_obj

                valid_pairs_count = sum(
                    1 for f in matching_formset if not f.cleaned_data.get("DELETE")
                )
                if valid_pairs_count >= 2:
                    question.save()
                    matching_formset.instance = question
                    matching_formset.save()
                    _save_matching_rights(question, request)
                    if test_obj:
                        messages.success(
                            request,
                            "Matching question added successfully to "
                            + test_obj.name
                            + ".",
                        )
                        return redirect(
                            reverse("custom_admin_test_questions", args=[test_obj.id])
                        )
                    else:
                        messages.success(
                            request, "Matching question added successfully."
                        )
                        next_url = request.POST.get("next") or request.GET.get("next")
                        if next_url:
                            return redirect(next_url)
                        return redirect("custom_admin_questions")
                else:
                    form.add_error(None, "Please provide at least 2 matching pairs.")
            else:
                if not form.is_valid():
                    messages.error(
                        request, "Please correct the errors in the question form."
                    )
                if not matching_formset.is_valid():
                    messages.error(
                        request, "Please correct the errors in the matching pairs."
                    )

    else:  # GET
        form = QuestionForm(initial=initial_data)
        formset = AnswerInlineFormSet()
        matching_formset = MatchingPairInlineFormSet()

    context = {
        "form": form,
        "formset": formset,
        "matching_formset": matching_formset,
        "is_edit": False,
        "test_obj": test_obj,
    }
    return render(request, "quiz/custom_admin/question_form.html", context)


@user_passes_test(is_staff_check)
def custom_admin_edit_question(request, question_id):
    question = get_object_or_404(Question, id=question_id)
    EditAnswerInlineFormSet = inlineformset_factory(
        Question, Answer, form=AnswerForm, extra=0, can_delete=True
    )
    EditMatchingPairInlineFormSet = inlineformset_factory(
        Question, MatchingPair, form=MatchingPairForm, extra=0, can_delete=True
    )

    if request.method == "POST":
        form = QuestionForm(request.POST, request.FILES, instance=question)
        question_type = request.POST.get("question_type", question.question_type)

        if question_type == "mc":
            formset = EditAnswerInlineFormSet(
                request.POST, request.FILES, instance=question
            )
            matching_formset = EditMatchingPairInlineFormSet(instance=question)
        else:
            formset = EditAnswerInlineFormSet(instance=question)
            matching_formset = EditMatchingPairInlineFormSet(
                request.POST, request.FILES, instance=question
            )

        if question_type == "mc":
            if form.is_valid() and formset.is_valid():
                answers_data = formset.cleaned_data
                has_correct_answer = any(
                    answer.get("is_correct")
                    for answer in answers_data
                    if not answer.get("DELETE")
                )
                if has_correct_answer:
                    valid_answers_count = sum(
                        1 for f in formset if not f.cleaned_data.get("DELETE")
                    )
                    if valid_answers_count >= 2:
                        form.save()
                        formset.save()
                        messages.success(request, "Question updated successfully.")
                        next_url = request.POST.get("next") or request.GET.get("next")
                        if next_url:
                            return redirect(next_url)
                        return redirect("custom_admin_questions")
                    else:
                        form.add_error(None, "Please ensure at least 2 answers.")
                else:
                    form.add_error(None, "Please mark at least one answer as correct.")
            else:
                if not form.is_valid():
                    messages.error(
                        request, "Please correct the errors in the question form."
                    )
                if not formset.is_valid():
                    messages.error(request, "Please correct the errors in the answers.")
        else:
            # Matching question
            if form.is_valid() and matching_formset.is_valid():
                valid_pairs_count = sum(
                    1 for f in matching_formset if not f.cleaned_data.get("DELETE")
                )
                if valid_pairs_count >= 2:
                    form.save()
                    matching_formset.save()
                    _save_matching_rights(question, request)
                    messages.success(request, "Matching question updated successfully.")
                    next_url = request.POST.get("next") or request.GET.get("next")
                    if next_url:
                        return redirect(next_url)
                    return redirect("custom_admin_questions")
                else:
                    form.add_error(None, "Please provide at least 2 matching pairs.")
            else:
                if not form.is_valid():
                    messages.error(
                        request, "Please correct the errors in the question form."
                    )
                if not matching_formset.is_valid():
                    messages.error(
                        request, "Please correct the errors in the matching pairs."
                    )

    else:  # GET
        form = QuestionForm(instance=question)
        if question.is_multiple_choice:
            formset = EditAnswerInlineFormSet(instance=question)
            matching_formset = EditMatchingPairInlineFormSet()
        else:
            formset = EditAnswerInlineFormSet()
            matching_formset = EditMatchingPairInlineFormSet(instance=question)

    context = {
        "form": form,
        "formset": formset,
        "matching_formset": matching_formset,
        "question": question,
        "is_edit": True,
    }
    return render(request, "quiz/custom_admin/question_form.html", context)


@user_passes_test(is_staff_check)
def custom_admin_delete_question(request, question_id):
    question = get_object_or_404(Question, id=question_id)
    next_url = request.GET.get("next") or request.POST.get("next")
    redirect_url = next_url if next_url else reverse("custom_admin_questions")
    if request.method == "POST":
        question.delete()
        messages.success(
            request, f"Question '{question.text[:30]}...' deleted successfully."
        )
        return redirect(redirect_url)
    # Confirmation page, pass redirect_url for cancel button
    return render(
        request,
        "quiz/custom_admin/question_confirm_delete.html",
        {"question": question, "redirect_url": redirect_url},
    )


@user_passes_test(is_staff_check)
def custom_admin_users(request):
    filter_status = request.GET.get("status", "all")
    search_query = request.GET.get("q", "")

    users_queryset = User.objects.select_related("userprofile").order_by("username")

    if search_query:
        users_queryset = users_queryset.filter(
            username__icontains=search_query
        ) | users_queryset.filter(email__icontains=search_query)

    if filter_status == "staff":
        users_queryset = users_queryset.filter(is_staff=True)
    elif filter_status == "normal":
        users_queryset = users_queryset.filter(is_staff=False)
    elif filter_status == "blocked":
        users_queryset = users_queryset.filter(
            userprofile__blocked_until__isnull=False,
            userprofile__blocked_until__gt=timezone.now(),
        )
    elif filter_status == "active":
        users_queryset = users_queryset.filter(
            userprofile__blocked_until__isnull=True
        ) | users_queryset.filter(
            userprofile__blocked_until__lt=timezone.now()
        )  # not blocked or block expired

    context = {
        "users": users_queryset,
        "filter_status": filter_status,
        "search_query": search_query,
        "now": timezone.now(),  # Pass current time for template logic
    }
    return render(request, "quiz/custom_admin/users_list.html", context)


# --- Custom Admin Views (Tests) ---


@user_passes_test(is_staff_check)
def custom_admin_tests(request):
    """List all Test types"""
    # --- MODIFIED: Annotate tests with question_count ---
    tests = Test.objects.annotate(question_count=Count("questions")).order_by("name")
    # --- END MODIFIED ---
    context = {
        "tests": tests,
    }
    return render(request, "quiz/custom_admin/admin_tests_list.html", context)


@user_passes_test(is_staff_check)
def custom_admin_add_test(request):
    """Add a new Test type"""
    if request.method == "POST":
        form = TestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Test added successfully.")
            return redirect("custom_admin_tests")  # Redirect back to the list
    else:  # GET request
        form = TestForm()

    context = {
        "form": form,
        "is_edit": False,  # Flag to indicate whether we're adding or editing
    }
    return render(request, "quiz/custom_admin/test_form.html", context)


@user_passes_test(is_staff_check)
def custom_admin_edit_test(request, test_id):
    """Edit an existing Test type"""
    test = get_object_or_404(Test, id=test_id)

    if request.method == "POST":
        form = TestForm(request.POST, instance=test)  # Pass instance for editing
        if form.is_valid():
            form.save()
            messages.success(request, "Test updated successfully.")
            return redirect("custom_admin_tests")  # Redirect back to the list
    else:  # GET request
        form = TestForm(instance=test)  # Populate form with existing data

    context = {
        "form": form,
        "test": test,  # Pass the test object
        "is_edit": True,  # Flag to indicate whether we're adding or editing
    }
    return render(request, "quiz/custom_admin/test_form.html", context)


@user_passes_test(is_staff_check)
def custom_admin_delete_test(request, test_id):
    """Delete a Test type"""
    test = get_object_or_404(Test, id=test_id)

    if request.method == "POST":
        test.delete()
        messages.success(request, f'Test "{test.name}" deleted successfully.')
        return redirect("custom_admin_tests")  # Redirect back to the list

    # GET request for confirmation page (optional but recommended)
    context = {
        "test": test,
    }
    return render(request, "quiz/custom_admin/test_confirm_delete.html", context)


@user_passes_test(is_staff_check)
def custom_admin_delete_user(request, user_id):
    user_to_delete = get_object_or_404(User, id=user_id)
    # Prevent superuser from deleting themselves or other superusers without extra confirmation
    if user_to_delete.is_superuser and not request.user.is_superuser:
        messages.error(request, "Only a superuser can delete another superuser.")
        return redirect("custom_admin_users")
    if user_to_delete == request.user:
        messages.error(request, "You cannot delete your own account from here.")
        return redirect("custom_admin_users")

    if request.method == "POST":
        user_to_delete.delete()
        messages.success(
            request, f"User '{user_to_delete.username}' deleted successfully."
        )
        return redirect("custom_admin_users")

    context = {"user_to_delete": user_to_delete}
    return render(request, "quiz/custom_admin/user_confirm_delete.html", context)


@user_passes_test(is_staff_check)
def custom_admin_block_user(request, user_id):
    user_to_block = get_object_or_404(User, id=user_id)
    # Get or create UserProfile for the user
    # Note: UserProfile should automatically be created via signal, so .userprofile should exist
    user_profile = user_to_block.userprofile

    # Prevent blocking yourself or other superusers unless specific logic
    if user_to_block == request.user:
        messages.error(request, "You cannot block your own account.")
        return redirect("custom_admin_users")
    if user_to_block.is_superuser and not request.user.is_superuser:
        messages.error(request, "Only a superuser can block another superuser.")
        return redirect("custom_admin_users")

    if request.method == "POST":
        form = UserBlockForm(
            request.POST, instance=user_profile
        )  # Target UserProfile instance
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"User '{user_to_block.username}' blocked until {user_profile.blocked_until}.",
            )
            return redirect("custom_admin_users")
        else:
            # If form is invalid, re-render with errors
            messages.error(request, "Please correct the form errors.")
    else:
        form = UserBlockForm(instance=user_profile)  # Pre-fill if already blocked

    context = {
        "user_to_block": user_to_block,
        "form": form,
        "now": timezone.now(),  # Pass current time for template logic
    }
    return render(request, "quiz/custom_admin/user_block_form.html", context)


@user_passes_test(is_staff_check)
def custom_admin_unblock_user(request, user_id):
    user_to_unblock = get_object_or_404(User, id=user_id)
    user_profile = user_to_unblock.userprofile
    if request.method == "POST":
        user_profile.blocked_until = None  # Set to None to unblock
        user_profile.save()
        messages.success(request, f"User '{user_to_unblock.username}' unblocked.")
        return redirect("custom_admin_users")
    messages.info(
        request, "Please confirm unblock via POST request."
    )  # This message should only appear if somehow accessed via GET
    return redirect("custom_admin_users")


@user_passes_test(is_staff_check)
def custom_admin_toggle_staff(request, user_id):
    user_to_toggle = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        # Prevent staff from removing own staff status, or affecting superusers without specific logic
        if user_to_toggle == request.user and not request.user.is_superuser:
            messages.error(
                request,
                "You cannot change your own staff status from here unless you are a superuser.",
            )
            return redirect("custom_admin_users")
        if user_to_toggle.is_superuser and not request.user.is_superuser:
            messages.error(
                request,
                "Only a superuser can change staff status of another superuser.",
            )
            return redirect("custom_admin_users")

        user_to_toggle.is_staff = not user_to_toggle.is_staff
        user_to_toggle.save()
        status = "granted" if user_to_toggle.is_staff else "revoked"
        messages.success(
            request, f"Staff status for '{user_to_toggle.username}' has been {status}."
        )
        return redirect("custom_admin_users")
    # Fallback for GET request if someone tries to access directly
    messages.info(request, "User staff status can only be toggled via POST.")
    return redirect("custom_admin_users")


@user_passes_test(is_staff_check)
def custom_admin_toggle_superuser(request, user_id):
    user_to_toggle = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        # Superuser only can toggle other superusers, and cannot remove own superuser status easily
        if user_to_toggle == request.user:
            messages.error(
                request, "You cannot change your own superuser status from here."
            )
            return redirect("custom_admin_users")
        if not request.user.is_superuser:
            messages.error(request, "Only a superuser can change superuser status.")
            return redirect("custom_admin_users")

        user_to_toggle.is_superuser = not user_to_toggle.is_superuser
        user_to_toggle.save()
        status = "granted" if user_to_toggle.is_superuser else "revoked"
        messages.success(
            request,
            f"Superuser status for '{user_to_toggle.username}' has been {status}.",
        )
        return redirect("custom_admin_users")
    # Fallback for GET request
    messages.info(request, "User superuser status can only be toggled via POST.")
    return redirect("custom_admin_users")
