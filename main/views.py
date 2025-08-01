from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.http import JsonResponse
from .models import User, Order, Category, Review, Portfolio, Tariff, BusyDate, Message, OrderResponse, OTP, BookingProposal, ServiceType, City
from .forms import UserRegistrationForm, UserProfileForm, OrderForm, ReviewForm, PortfolioForm, TariffForm
from .services import WhatsAppOTPService
import json
from datetime import datetime, timedelta, date
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from decimal import Decimal



def index(request):
    if request.user.is_authenticated and request.user.user_type in ['performer', 'customer']:
        return redirect('main:dashboard')
    
    # Получаем 10 последних зарегистрированных исполнителейss
    latest_performers = User.objects.filter(
        user_type='performer',
        is_active=True
    ).order_by('-date_joined')[:10]
    
    return render(request, 'index.html', {
        'latest_performers': latest_performers
    })

def auth_page(request):
    """Render the authentication page"""
    if request.user.is_authenticated and request.user.user_type in ['performer', 'customer']:
        return redirect('main:dashboard')
    
    # Получаем города из базы данных
    cities = City.objects.filter(is_active=True).order_by('name')
    
    # Получаем типы услуг из базы данных
    service_types = ServiceType.objects.filter(is_active=True).order_by('sort_order')
    
    return render(request, 'auth.html', {
        'cities': cities,
        'service_types': service_types
    })

def register(request):
    if request.method == 'POST':
        print('REGISTER POST DATA:', dict(request.POST))
        user_type = request.POST.get('user_type')
        service_type = request.POST.get('service_type') if user_type == 'performer' else None
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_number = request.POST.get('phone_number')
        city = request.POST.get('city')
        
        # Проверка обязательных полей
        if not first_name or not last_name or not phone_number or not user_type or not city:
            msg = 'Пожалуйста, заполните все обязательные поля.'
            print('REGISTER ERROR:', msg)
            messages.error(request, msg)
            return redirect('main:auth')
        
        # Проверяем, существует ли такой город в базе данных
        try:
            city_obj = City.objects.get(name=city)
        except City.DoesNotExist:
            msg = 'Выберите корректный город!'
            print('REGISTER ERROR:', msg)
            messages.error(request, msg)
            return redirect('main:auth')
            
        if user_type == 'performer' and service_type:
            # Проверяем, существует ли такой тип услуги в базе данных
            try:
                service_type_obj = ServiceType.objects.get(code=service_type)
            except ServiceType.DoesNotExist:
                msg = 'Выберите корректную специализацию исполнителя!'
                print('REGISTER ERROR:', msg)
                messages.error(request, msg)
                return redirect('main:auth')
        
        # Проверяем, не занят ли номер телефона
        if User.objects.filter(phone_number=phone_number).exists():
            msg = 'Пользователь с таким номером телефона уже существует!'
            print('REGISTER ERROR:', msg)
            messages.error(request, msg)
            return redirect('main:auth')
        # Создание пользователя
        try:
            # Генерируем уникальный username на основе телефона
            username = f"user_{phone_number.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')}"
            
            # Генерируем случайный пароль (пользователь будет входить по номеру телефона)
            import random
            import string
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            user = User.objects.create_user(
                username=username,
                phone_number=phone_number,
                first_name=first_name,
                last_name=last_name,
                city=city_obj,
                user_type=user_type,
                service_type=service_type_obj if user_type == 'performer' and service_type else None,
                is_phone_verified=True,
                email=f"{username}@example.com",  # Временный email
                password=password,
            )
            if user_type == 'performer':
                user.company_name = request.POST.get('company_name', '')
                user.bio = request.POST.get('bio', '')
            if request.FILES.get('profile_photo'):
                user.profile_photo = request.FILES['profile_photo']
            user.save()
            print('REGISTER SUCCESS: user created successfully')
            
            # Автоматически входим в систему
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно!')
            return redirect('main:dashboard')
            
        except Exception as e:
            msg = f'Ошибка при создании пользователя: {str(e)}'
            print('REGISTER ERROR:', msg)
            messages.error(request, msg)
            return redirect('main:auth')
    # Получаем города из базы данных
    cities = City.objects.filter(is_active=True).order_by('name')
    
    # Получаем типы услуг из базы данных
    service_types = ServiceType.objects.filter(is_active=True).order_by('sort_order')
    
    return render(request, 'auth.html', {
        'is_register': True,
        'cities': cities,
        'service_types': service_types
    })

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if not username or not password:
            messages.error(request, 'Пожалуйста, введите логин и пароль.')
            return render(request, 'auth.html', {'is_register': False})
            
        # Сначала пробуем аутентифицировать напрямую (если введен username)
        user = authenticate(request, username=username, password=password)
        
        if user is None:
            try:
                # Если не получилось, ищем пользователя по email
                users = User.objects.filter(email=username)
                if users.count() > 1:
                    messages.error(request, 'Найдено несколько пользователей с таким email. Пожалуйста, используйте имя пользователя для входа.')
                    return render(request, 'auth.html', {'is_register': False})
                elif users.exists():
                    # Пробуем аутентифицировать по найденному username
                    user = authenticate(request, username=users.first().username, password=password)
                else:
                    messages.error(request, 'Пользователь не найден.')
                    return render(request, 'auth.html', {'is_register': False})
            except Exception as e:
                messages.error(request, 'Произошла ошибка при попытке входа.')
                return render(request, 'auth.html', {'is_register': False})
        
        if user is not None:
            login(request, user)
            messages.success(request, 'Вы успешно вошли в систему!')
            return redirect('main:dashboard')
        else:
            messages.error(request, 'Неверный пароль.')
            
    return render(request, 'auth.html', {'is_register': False})

@login_required
def profile(request):
    if request.method == 'POST':
        try:
            print(f"PROFILE UPDATE - POST data: {dict(request.POST)}")
            print(f"PROFILE UPDATE - FILES: {dict(request.FILES)}")
            
            # Update basic user information
            request.user.first_name = request.POST.get('first_name', '')
            request.user.last_name = request.POST.get('last_name', '')
            
            # Check email uniqueness
            new_email = request.POST.get('email', '')
            if new_email != request.user.email:
                if User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
                    raise ValueError('Пользователь с таким email уже существует')
            request.user.email = new_email
            
            city_name = request.POST.get('city', '')
            if city_name:
                try:
                    city_obj = City.objects.get(name=city_name)
                    request.user.city = city_obj
                except City.DoesNotExist:
                    messages.error(request, 'Выберите корректный город!')
                    return redirect('main:profile')
            else:
                request.user.city = None
            request.user.phone_number = request.POST.get('phone', '')
        
            # Update performer-specific fields if applicable
            if request.user.user_type == 'performer':
                request.user.company_name = request.POST.get('company_name', '')
                request.user.service_type = request.POST.get('service_type', '')
                request.user.bio = request.POST.get('bio', '')
        
            # Handle profile photo upload
            if request.FILES.get('profile_photo'):
                request.user.profile_photo = request.FILES['profile_photo']
        
            print(f"PROFILE UPDATE - Before save: user={request.user.id}, email={request.user.email}, phone={request.user.phone_number}")
            request.user.save()
            print(f"PROFILE UPDATE - After save: success")
            
            # Check if it's an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Профиль успешно обновлен'})
            
            messages.success(request, 'Профиль успешно обновлен')
            return redirect('main:profile')
        except Exception as e:
            print(f"PROFILE UPDATE - ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Check if it's an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Ошибка при сохранении профиля: {str(e)}'})
            
            messages.error(request, f'Ошибка при сохранении профиля: {str(e)}')
            return redirect('main:profile')
        
    context = {
        'user': request.user,
        'subscription_plans': [
            {
                'id': 'monthly',
                'name': 'Месячный тариф',
                'price': 10000,
                'duration': '1 месяц'
            },
            {
                'id': 'quarterly',
                'name': 'Квартальный тариф',
                'price': 25000,
                'duration': '3 месяца'
            }
        ],
        'kaspi_payment_url': 'https://pay.kaspi.kz/pay/96yxytne'
    }
    if request.user.user_type == 'performer':
        active_orders = []
        extra_orders = Order.objects.filter(
            status__in=['in_progress', 'new'],
            order_type='request'
        )
        for order in extra_orders:
            selected = order.selected_performers or {}
            # Исправленная логика:
            if selected:
                if str(selected.get(request.user.service_type.code if request.user.service_type else None)) == str(request.user.id):
                    active_orders.append(order)
            else:
                # Только если performer_id совпадает и услуга реально есть в заказе
                if order.performer_id == request.user.id and (request.user.service_type.code if request.user.service_type else None) in (order.services or []):
                    active_orders.append(order)
        active_orders = sorted(active_orders, key=lambda o: o.created_at, reverse=True)
        context['active_orders'] = active_orders
    # Получаем типы услуг для модального окна
    service_types = ServiceType.objects.filter(is_active=True).order_by('sort_order')
    context['service_types'] = service_types
    
    # Получаем города для модального окна
    cities = City.objects.filter(is_active=True).order_by('name')
    context['cities'] = cities
    
    return render(request, 'profile.html', context)

@login_required
def process_subscription(request):
    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        if plan_id not in ['monthly', 'quarterly']:
            messages.error(request, 'Неверный тариф')
            return redirect('main:dashboard')
            
        # Redirect to Kaspi payment
        return redirect('https://pay.kaspi.kz/pay/96yxytne')
    return redirect('main:dashboard')

def view_profile(request, user_id):
    user = get_object_or_404(User, id=user_id)
    busy_dates = BusyDate.objects.filter(user=user).order_by('date')
    tariffs = Tariff.objects.filter(user=user).order_by('price')
    return render(request, 'profile.html', {
        'profile_user': user,
        'is_own_profile': request.user == user if request.user.is_authenticated else False,
        'busy_dates': busy_dates,
        'tariffs': tariffs
    })

@login_required
def profile_settings(request):
    if request.method == 'POST':
        # Получаем данные из формы
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        city_name = request.POST.get('city', '').strip()
        
        # Проверяем обязательные поля
        if not first_name or not last_name or not email:
            error_message = 'Пожалуйста, заполните все обязательные поля.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_message
                })
            messages.error(request, error_message)
            return render(request, 'profile_settings.html', {'user': request.user})
        
        # Update basic user information
        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.email = email
        if city_name:
            try:
                city_obj = City.objects.get(name=city_name)
                request.user.city = city_obj
            except City.DoesNotExist:
                error_message = 'Выберите корректный город!'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({
                        'success': False,
                        'message': error_message
                    })
                messages.error(request, error_message)
                return render(request, 'profile_settings.html', {'user': request.user})
        else:
            request.user.city = None
        
        # Update performer-specific fields if applicable
        if request.user.user_type == 'performer':
            request.user.company_name = request.POST.get('company_name', '')
            service_type_code = request.POST.get('service_type', '')
            if service_type_code:
                try:
                    service_type_obj = ServiceType.objects.get(code=service_type_code)
                    request.user.service_type = service_type_obj
                except ServiceType.DoesNotExist:
                    error_message = 'Выберите корректную специализацию исполнителя!'
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        from django.http import JsonResponse
                        return JsonResponse({
                            'success': False,
                            'message': error_message
                        })
                    messages.error(request, error_message)
                    return render(request, 'profile_settings.html', {'user': request.user})
            else:
                request.user.service_type = None
            request.user.bio = request.POST.get('bio', '')
            request.user.services_description = request.POST.get('services_description', '')
            request.user.experience = request.POST.get('experience', '')
        
        # Update notification settings
        request.user.email_notifications = request.POST.get('email_notifications') == 'on'
        request.user.whatsapp_notifications = request.POST.get('whatsapp_notifications') == 'on'
        
        # Handle profile photo upload
        if request.FILES.get('profile_photo'):
            request.user.profile_photo = request.FILES['profile_photo']
        
        request.user.save()
        
        # Проверяем, является ли это AJAX-запросом
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({
                'success': True,
                'message': 'Профиль успешно обновлен'
            })
        
        messages.success(request, 'Профиль успешно обновлен')
        return redirect('main:profile_settings')
        
    # Получаем типы услуг из базы данных
    service_types = ServiceType.objects.filter(is_active=True).order_by('sort_order')
    
    # Получаем города из базы данных
    cities = City.objects.filter(is_active=True).order_by('name')
    
    return render(request, 'profile_settings.html', {
        'user': request.user,
        'service_types': service_types,
        'cities': cities
    })

@login_required
def dashboard(request):
    # Очищаем прошедшие занятые даты
    cleanup_past_busy_dates()
    
    if request.user.user_type == 'performer':
        # Получаем все новые заявки-запросы, на которые исполнитель еще не откликался
        all_orders = Order.objects.filter(
            status='new',
            order_type='request'
        ).exclude(
            responses__performer=request.user
        ).order_by('-created_at')

        # Фильтруем в Python: только те, где его специализация есть в services и по этой услуге еще не выбран исполнитель
        available_orders = []
        for order in all_orders:
            services = order.services or []
            selected = order.selected_performers or {}
            # Исполнитель видит заказ, если его услуга есть в заказе и по этой услуге еще не выбран исполнитель
            service_type_code = request.user.service_type.code if request.user.service_type else None
            if (
                service_type_code in services and
                (not selected.get(service_type_code))
            ):
                available_orders.append(order)
        
        # Получаем активные заказы исполнителя
        active_orders = []
        
        # 1. Прямые бронирования (order_type='booking')
        booking_orders = Order.objects.filter(
            performer=request.user,
            order_type='booking',
            status__in=['in_progress', 'new']
        )
        active_orders.extend(booking_orders)
        
        # 2. Заявки-запросы, где исполнитель выбран
        request_orders = Order.objects.filter(
            status__in=['in_progress', 'new'],
            order_type='request'
        )
        for order in request_orders:
            selected = order.selected_performers or {}
            # Показываем, если исполнитель выбран по своей услуге
            if str(selected.get(request.user.service_type.code if request.user.service_type else None)) == str(request.user.id):
                active_orders.append(order)
            # Для старых заказов (без selected_performers)
            elif not selected and order.performer_id == request.user.id and (request.user.service_type.code if request.user.service_type else None) in (order.services or []):
                active_orders.append(order)
        
        active_orders = sorted(active_orders, key=lambda o: o.created_at, reverse=True)
        
        # Получаем отклики исполнителя (только те, которые еще не приняты)
        my_responses = OrderResponse.objects.filter(
            performer=request.user
        ).select_related('order').order_by('-created_at')
        
        # Фильтруем отклики: убираем те, где заказ уже в работе и исполнитель выбран
        filtered_responses = []
        for response in my_responses:
            order = response.order
            if order.status == 'new':
                # Если заказ новый, показываем отклик
                filtered_responses.append(response)
            elif order.status == 'in_progress':
                # Если заказ в работе, проверяем, выбран ли исполнитель
                selected = order.selected_performers or {}
                service_type_code = request.user.service_type.code if request.user.service_type else None
                if service_type_code in selected and str(selected[service_type_code]) == str(request.user.id):
                    # Исполнитель выбран - не показываем в откликах
                    continue
                else:
                    # Исполнитель не выбран - показываем отклик
                    filtered_responses.append(response)
        
        my_responses = filtered_responses
        
        # Получаем предложения о бронировании (устаревший механизм)
        # booking_proposals = BookingProposal.objects.filter(
        #     performer=request.user,
        #     status='pending'
        # ).select_related('order', 'tariff').order_by('-created_at')
        
        # Получаем портфолио
        portfolio_photos = Portfolio.objects.filter(user=request.user).order_by('-id')
        
        # Получаем тарифы
        tariffs = Tariff.objects.filter(user=request.user).order_by('price')
        
        # Получаем занятые даты
        busy_dates = BusyDate.objects.filter(user=request.user).order_by('date')
        
        # Получаем статистику
        completed_orders_count = Order.objects.filter(
            performer=request.user,
            status='completed'
        ).count()
        
        # Получаем активные бронирования
        active_bookings_count = Order.objects.filter(
            performer=request.user,
            order_type='booking',
            status__in=['in_progress', 'new']
        ).count()
        
        all_orders_debug = Order.objects.filter(status__in=['in_progress', 'new'], order_type='request')
        
        # Получаем города и типы услуг для модальных окон
        cities = City.objects.filter(is_active=True).order_by('name')
        service_types = ServiceType.objects.filter(is_active=True).order_by('sort_order')
        
        return render(request, 'dashboard-performer.html', {
            'available_orders': available_orders,
            'active_orders': active_orders,
            'my_responses': my_responses,
            'portfolio_photos': portfolio_photos,
            'tariffs': tariffs,
            'busy_dates': busy_dates,
            'completed_orders_count': completed_orders_count,
            'active_bookings_count': active_bookings_count,
            'rating': request.user.rating,
            'all_orders_debug': all_orders_debug,
            'new_requests_count': len(available_orders),
            'cities': cities,
            'service_types': service_types,
        })
    elif request.user.user_type == 'customer':
        # Получаем все заказы клиента
        orders = Order.objects.filter(
            customer=request.user,
            status__in=['new', 'in_progress', 'completed']
        ).order_by('-created_at')
        
        # Получаем отклики на заказы клиента
        responses = OrderResponse.objects.filter(
            order__customer=request.user,
            order__status='new'
        ).select_related('order', 'performer').order_by('-created_at')
        
        # Получаем бронирования (прямые заказы исполнителей) - включаем отмененные
        bookings = Order.objects.filter(
            customer=request.user,
            order_type='booking',
            status__in=['new', 'in_progress', 'completed', 'cancelled']  # Включаем 'cancelled'
        ).select_related('performer').order_by('-created_at')
        
        # Статистика
        active_orders_count = Order.objects.filter(
            customer=request.user,
            status='in_progress'
        ).count()
        
        completed_orders_count = Order.objects.filter(
            customer=request.user,
            status='completed'
        ).count()
        
        responses_count = responses.count()
        bookings_count = bookings.count()
        
        # Подсчитываем общую сумму потраченную на завершенные заказы
        total_spent = OrderResponse.objects.filter(
            order__customer=request.user,
            order__status='completed'
        ).aggregate(total=models.Sum('price'))['total'] or 0
        
        # Добавляем сумму потраченную на бронирования
        bookings_spent = Order.objects.filter(
            customer=request.user,
            order_type='booking',
            status='completed'
        ).aggregate(total=models.Sum('budget_max'))['total'] or 0
        
        total_spent += bookings_spent
        
        # Получаем города и типы услуг для модальных окон
        cities = City.objects.filter(is_active=True).order_by('name')
        service_types = ServiceType.objects.filter(is_active=True).order_by('sort_order')
        
        # Получаем отзывы заказчика для проверки, какие заказы уже имеют отзывы
        customer_reviews = Review.objects.filter(
            from_user=request.user
        ).values_list('order_id', flat=True)
        
        return render(request, 'dashboard-customer.html', {
            'orders': orders,
            'responses': responses,
            'bookings': bookings,
            'active_orders_count': active_orders_count,
            'completed_orders_count': completed_orders_count,
            'responses_count': responses_count,
            'bookings_count': bookings_count,
            'total_spent': total_spent,
            'orders_count': orders.count(),
            'cities': cities,
            'service_types': service_types,
            'customer_reviews': customer_reviews,  # Передаем список ID заказов с отзывами
        })
    
    # Если пользователь не performer и не customer (например, админ), показываем главную страницу
    return redirect('main:catalog')

def catalog(request):
    # Базовый запрос исполнителей
    performers = User.objects.filter(user_type='performer', is_active=True)\
        .prefetch_related('tariffs', 'reviews_received')\
        .annotate(
            reviews_count=Count('reviews_received'),
            avg_rating=models.Avg('reviews_received__rating')
        )

    # Получаем фильтры из GET параметров
    category = request.GET.get('category')
    city = request.GET.get('city')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    rating = request.GET.get('rating')
    date = request.GET.get('date')
    sort = request.GET.get('sort', 'rating')

    # Применяем фильтры
    if category and category != 'all':
        performers = performers.filter(service_type__code=category)
    
    if city and city != '':
        performers = performers.filter(city__name__iexact=city)
    
    if min_price and min_price.isdigit():
        performers = performers.filter(tariffs__price__gte=int(min_price))
    
    if max_price and max_price.isdigit():
        performers = performers.filter(tariffs__price__lte=int(max_price))
    
    if rating and rating.isdigit():
        performers = performers.filter(avg_rating__gte=float(rating))
    
    if date and date.strip():
        try:
            # Проверяем, что дата в правильном формате
            from datetime import datetime
            parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
            performers = performers.exclude(busydate__date=parsed_date)
        except ValueError:
            # Если дата в неправильном формате, игнорируем фильтр
            pass

    # Убираем дубликаты после фильтрации
    performers = performers.distinct()

    # Применяем сортировку
    if sort == 'price_low':
        performers = performers.order_by('tariffs__price')
    elif sort == 'price_high':
        performers = performers.order_by('-tariffs__price')
    elif sort == 'rating':
        performers = performers.order_by('-avg_rating', '-reviews_count')
    elif sort == 'newest':
        performers = performers.order_by('-date_joined')
    else:
        performers = performers.order_by('-avg_rating', '-reviews_count')

    # Пагинация
    from django.core.paginator import Paginator
    paginator = Paginator(performers, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Убеждаемся, что performers содержит только элементы текущей страницы
    performers = page_obj.object_list

    # Получаем города из базы данных
    cities = City.objects.filter(is_active=True).order_by('name')

    # Получаем категории из базы данных
    categories = ServiceType.objects.filter(is_active=True).order_by('sort_order')

    # Подготавливаем контекст фильтров
    current_filters = {
        'category': category,
        'city': city,
        'min_price': min_price,
        'max_price': max_price,
        'rating': rating,
        'date': date,
        'sort': sort
    }

    context = {
        'performers': page_obj,
        'page_obj': page_obj,
        'cities': cities,
        'categories': categories,
        'current_filters': current_filters
    }
    
    return render(request, 'catalog.html', context)

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Проверяем, что пользователь имеет право просматривать заказ
    if request.user.user_type == 'performer':
        # Исполнители могут видеть новые заказы и свои заказы
        can_access = False
        if order.status == 'new':
            # Новые заказы может видеть любой исполнитель
            can_access = True
        elif order.performer == request.user:
            # Старые заказы (где performer установлен напрямую)
            can_access = True
        elif order.selected_performers:
            # Новые заказы с selected_performers
            selected_performers = order.selected_performers or {}
            if (request.user.service_type.code if request.user.service_type else None) in selected_performers:
                if str(selected_performers[request.user.service_type.code if request.user.service_type else None]) == str(request.user.id):
                    can_access = True
        
        if not can_access:
            messages.error(request, 'У вас нет доступа к этому заказу')
            return redirect('main:dashboard')
    elif request.user != order.customer:
        # Заказчики могут видеть только свои заказы
        messages.error(request, 'У вас нет доступа к этому заказу')
        return redirect('main:dashboard')
        
    if request.method == 'POST':
        if request.user.user_type == 'performer' and 'take_order' in request.POST:
            # Исполнитель откликается на заказ
            if order.status == 'new':
                try:
                    # Проверяем, не откликался ли уже исполнитель
                    if OrderResponse.objects.filter(order=order, performer=request.user).exists():
                        messages.error(request, 'Вы уже откликнулись на этот заказ')
                    else:
                        # Создаем отклик
                        response = OrderResponse.objects.create(
                            order=order,
                            performer=request.user,
                            message=request.POST.get('response_message', ''),
                            price=request.POST.get('response_price', 0)
                        )
                        messages.success(request, 'Ваш отклик успешно отправлен')
                except Exception as e:
                    messages.error(request, 'Произошла ошибка при отправке отклика')
            else:
                messages.error(request, 'Этот заказ уже не доступен для отклика')
        
        elif request.user == order.customer:
            if 'accept_response' in request.POST:
                # Заказчик принимает отклик
                response_id = request.POST.get('response_id')
                try:
                    response = OrderResponse.objects.get(id=response_id, order=order)
                    # Проверка: исполнитель не должен быть уже выбран и заказ должен быть новым
                    if order.performer is not None or order.status != 'new':
                        return redirect('main:order_detail', order_id=order.id)
                    else:
                        # Получаем специализацию исполнителя
                        service_type = response.performer.service_type.code if response.performer.service_type else None
                        selected_performers = order.selected_performers or {}
                        selected_performers[service_type] = response.performer.id
                        order.selected_performers = selected_performers
                        if set(selected_performers.keys()) == set(order.services):
                            order.status = 'in_progress'
                            order.save()
                        else:
                            order.save()
                        # Удаляем все остальные отклики по этой услуге
                        OrderResponse.objects.filter(order=order, performer__service_type__code=service_type).exclude(id=response_id).delete()
                        messages.success(request, f'Исполнитель по услуге {service_type} успешно выбран')
                        
                        # Создаем первое сообщение в чате от заказчика
                        Message.objects.create(
                            order=order,
                            from_user=request.user,
                            to_user=response.performer,
                            content=f'Здравствуйте! Я выбрал вас для выполнения услуги "{service_type}". Давайте обсудим детали.'
                        )
                except OrderResponse.DoesNotExist:
                    messages.error(request, 'Отклик не найден')
            
            elif 'reject_response' in request.POST:
                # Заказчик отклоняет отклик
                response_id = request.POST.get('response_id')
                try:
                    response = OrderResponse.objects.get(id=response_id, order=order)
                    response.delete()
                    messages.success(request, 'Отклик отклонен')
                except OrderResponse.DoesNotExist:
                    messages.error(request, 'Отклик не найден')
            
    # Получаем отклики для заказа
    if order.status == 'new':
        responses = OrderResponse.objects.filter(order=order).select_related('performer')
    else:
        responses = None

    # Фильтруем отклики: показываем только тех, кто ещё не выбран по своей услуге
    unselected_responses = []
    if responses:
        selected = order.selected_performers or {}
        for r in responses:
            # Если услуга не выбрана или выбран другой исполнитель
            service_type_code = r.performer.service_type.code if r.performer.service_type else None
            if service_type_code not in selected or selected[service_type_code] != r.performer.id:
                unselected_responses.append(r)

    is_selected_performer = False
    if request.user.user_type == 'performer' and order.selected_performers:
        service_type_code = request.user.service_type.code if request.user.service_type else None
        if service_type_code in order.selected_performers and order.selected_performers[service_type_code] == request.user.id:
            is_selected_performer = True
    can_take_order = (
        request.user.user_type == 'performer'
        and order.status == 'new'
        and (
            not order.selected_performers
            or request.user.service_type not in order.selected_performers
        )
    )
    # Получаем типы услуг из базы данных
    service_types = ServiceType.objects.filter(is_active=True).order_by('sort_order')
    
    # Создаем словарь для быстрого поиска услуг по коду
    service_types_dict = {st.code: st for st in service_types}
    
    context = {
        'order': order,
        'can_take_order': can_take_order,
        'is_performer': request.user == order.performer,
        'is_customer': request.user == order.customer,
        'responses': unselected_responses if request.user == order.customer else None,
        'performers_by_id': {pid: User.objects.filter(id=pid).first() for pid in (order.selected_performers or {}).values()} if order.selected_performers else {},
        'is_selected_performer': is_selected_performer,
        'service_types': service_types,
        'service_types_dict': service_types_dict,
    }
            
    return render(request, 'order_detail.html', context)

@login_required
def create_order_request(request):
    """Создание заявки заказчиком"""
    if request.method == 'POST':
        if request.user.user_type != 'customer':
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Только заказчики могут создавать заявки'}, status=403)
            messages.error(request, 'Только заказчики могут создавать заявки')
            return redirect('main:dashboard')
            
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.customer = request.user
            order.order_type = 'request'
            order.status = 'new'
            
            # Получаем город из формы
            city_name = form.cleaned_data.get('city')
            order.city = city_name
            
            services = request.POST.get('services', '[]')
            try:
                order.services = json.loads(services)
            except json.JSONDecodeError:
                order.services = []
                
            order.save()
            
            # Если это AJAX-запрос, возвращаем JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Заявка успешно создана',
                    'order_id': order.id
                })
            
            messages.success(request, 'Заявка успешно создана')
            return redirect('main:order_detail', order.id)
        else:
            # Если это AJAX-запрос, возвращаем ошибки в JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errors = {}
                for field, field_errors in form.errors.items():
                    errors[field] = field_errors[0] if field_errors else 'Ошибка валидации'
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                    'message': 'Пожалуйста, исправьте ошибки в форме'
                }, status=400)
            
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме')
    else:
        form = OrderForm()
    
    # Получаем типы услуг из базы данных
    service_types = ServiceType.objects.filter(is_active=True).order_by('sort_order')
    
    return render(request, 'order.html', {
        'form': form,
        'is_edit': False,
        'service_types': service_types
    })

@login_required
def create_order_booking(request, performer_id):
    """Бронирование исполнителя"""
    if request.method == 'POST':
        performer = get_object_or_404(User, id=performer_id, user_type='performer')
        
        # Проверяем, что пользователь является заказчиком
        if request.user.user_type != 'customer':
            messages.error(request, 'Только заказчики могут создавать заявки')
            return redirect('main:profile', performer_id)
            
        # Получаем данные из формы
        event_date_str = request.POST.get('event_date')
        tariff_id = request.POST.get('tariff')
        details = request.POST.get('details')
        order_id = request.POST.get('order_id')  # ID существующей заявки
        
        # Парсим дату с учетом часового пояса
        try:
            from django.utils import timezone
            
            # Парсим дату и создаем datetime в текущем часовом поясе
            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            
            # Отладочная информация
            print(f"DEBUG: Исходная дата: {event_date_str}")
            print(f"DEBUG: Parsed date: {event_date}")
            print(f"DEBUG: Current timezone: {timezone.get_current_timezone()}")
            print(f"DEBUG: Current date: {timezone.now().date()}")
            
            # Проверяем, что дата не в прошлом
            if event_date < timezone.now().date():
                messages.error(request, 'Нельзя выбрать прошедшую дату')
                return redirect('main:profile', performer_id)
                
            # Проверяем, что дата не слишком далеко в будущем
            max_date = timezone.now().date() + timedelta(days=180)  # 6 месяцев
            if event_date > max_date:
                messages.error(request, 'Нельзя бронировать более чем на 6 месяцев вперед')
                return redirect('main:profile', performer_id)
                
            # Проверяем, что дата не занята
            if BusyDate.objects.filter(user=performer, date=event_date).exists():
                messages.error(request, 'Эта дата уже занята')
                return redirect('main:profile', performer_id)
                
        except ValueError:
            messages.error(request, 'Неверный формат даты')
            return redirect('main:profile', performer_id)
        
        # Получаем тариф
        try:
            tariff = Tariff.objects.get(id=tariff_id, user=performer)
        except Tariff.DoesNotExist:
            messages.error(request, 'Выбранный тариф не существует')
            return redirect('main:profile', performer_id)
        
        # Если указан ID заявки, прикрепляем исполнителя к существующей заявке
        if order_id:
            try:
                order = Order.objects.get(id=order_id, customer=request.user, status='new')
                order.performer = performer
                order.event_date = event_date
                order.tariff = tariff
                order.details = details
                order.status = 'new'  # Статус "новый" - исполнитель должен принять/отклонить
                order.order_type = 'booking'
                order.save()
                
                # Добавляем дату в занятые (если еще не занята)
                if not BusyDate.objects.filter(user=performer, date=event_date).exists():
                    BusyDate.objects.create(user=performer, date=event_date)
                
                messages.success(request, 'Исполнитель успешно прикреплен к заявке')
                return redirect('main:dashboard')
                
            except Order.DoesNotExist:
                messages.error(request, 'Заявка не найдена или недоступна')
                return redirect('main:view_profile', user_id=performer_id)
        else:
            # Создаем новое бронирование
            order = Order.objects.create(
                customer=request.user,
                performer=performer,
                title=f'Заказ на {event_date}',
                event_type='other',
                event_date=event_date,
                city=performer.city,
                venue='',
                guest_count=1,
                description=details,
                budget_min=tariff.price,
                budget_max=tariff.price,
                services=[],  # Пустой список услуг, так как это бронирование
                tariff=tariff,
                details=details,
                order_type='booking',  # Указываем, что это бронирование
                status='new'  # Статус "новый" - исполнитель должен принять/отклонить
            )
            
            # Добавляем дату в занятые (если еще не занята)
            if not BusyDate.objects.filter(user=performer, date=event_date).exists():
                BusyDate.objects.create(user=performer, date=event_date)
            
            messages.success(request, 'Бронирование успешно создано')
            return redirect('main:dashboard')
        
    return redirect('main:view_profile', user_id=performer_id)

@login_required
def create_review(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.order = order
            review.from_user = request.user
            review.to_user = order.performer if request.user == order.customer else order.customer
            review.save()
            messages.success(request, 'Review submitted successfully')
            return redirect('main:order_detail', order_id=order_id)
    else:
        form = ReviewForm()
    return render(request, 'order.html', {'form': form, 'order': order})

@login_required
def edit_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.user != order.customer:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'У вас нет прав для редактирования этого заказа'}, status=403)
        messages.error(request, 'У вас нет прав для редактирования этого заказа')
        return redirect('main:dashboard')
        
    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save(commit=False)
            
            # Получаем город из формы
            city_name = form.cleaned_data.get('city')
            order.city = city_name
            
            services = request.POST.get('services', '[]')
            try:
                order.services = json.loads(services)
            except json.JSONDecodeError:
                order.services = []
            order.save()
            
            # Если это AJAX-запрос, возвращаем JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Заказ успешно обновлен!',
                    'order_id': order.id
                })
            
            messages.success(request, 'Заказ успешно обновлен!')
            return redirect('main:order_detail', order_id=order.id)
        else:
            # Если это AJAX-запрос, возвращаем ошибки в JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errors = {}
                for field, field_errors in form.errors.items():
                    errors[field] = field_errors[0] if field_errors else 'Ошибка валидации'
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                    'message': 'Пожалуйста, исправьте ошибки в форме'
                }, status=400)
    else:
        form = OrderForm(instance=order)
    
    # Получаем типы услуг из базы данных
    service_types = ServiceType.objects.filter(is_active=True).order_by('sort_order')
    
    return render(request, 'order.html', {
        'form': form,
        'order': order,
        'is_edit': True,
        'service_types': service_types
    })

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.user != order.customer:
        messages.error(request, 'У вас нет прав для отмены этого заказа')
        return redirect('main:dashboard')
    
    if request.method == 'POST':
        # Удаляем дату из занятых при отмене заказа
        if order.performer:
            BusyDate.objects.filter(user=order.performer, date=order.event_date).delete()
        
        order.status = 'cancelled'
        order.save()
        messages.success(request, 'Заказ успешно отменен')
        return redirect('main:dashboard')
        
    return render(request, 'cancel_order.html', {'order': order})

@login_required
def delete_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.user != order.customer:
        messages.error(request, 'У вас нет прав для удаления этого заказа')
        return redirect('main:dashboard')
    
    if request.method == 'POST':
        # Удаляем дату из занятых при удалении заказа
        if order.performer:
            BusyDate.objects.filter(user=order.performer, date=order.event_date).delete()
        
        order.delete()
        messages.success(request, 'Заказ успешно удален')
        return redirect('main:dashboard')
        
    return render(request, 'delete_order.html', {'order': order})

@login_required
def performer_cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Проверяем права доступа
    if request.user.user_type != 'performer':
        return JsonResponse({'success': False, 'error': 'Только исполнители могут отменять заказы'}, status=403)
    
    # Проверяем, является ли исполнитель выбранным для этого заказа
    is_selected = False
    if order.order_type == 'booking' and order.performer == request.user:
        is_selected = True
    elif order.order_type == 'request' and order.selected_performers:
        selected = order.selected_performers or {}
        service_type_code = request.user.service_type.code if request.user.service_type else None
        if service_type_code in selected and str(selected[service_type_code]) == str(request.user.id):
            is_selected = True
    
    if not is_selected:
        return JsonResponse({'success': False, 'error': 'У вас нет прав для отмены этого заказа'}, status=403)
    
    if request.method == 'POST':
        try:
            # Удаляем дату из занятых при отмене участия исполнителя
            BusyDate.objects.filter(user=request.user, date=order.event_date).delete()
            
            # Удаляем отклик исполнителя на этот заказ
            OrderResponse.objects.filter(order=order, performer=request.user).delete()
            
            if order.order_type == 'booking':
                # Для прямых бронирований
                order.performer = None
                order.status = 'new'
            elif order.order_type == 'request':
                # Для заявок-запросов
                selected = order.selected_performers or {}
                service_type_code = request.user.service_type.code if request.user.service_type else None
                if service_type_code in selected:
                    del selected[service_type_code]
                    order.selected_performers = selected
                    # Если больше нет выбранных исполнителей, возвращаем статус в 'new'
                    if not selected:
                        order.status = 'new'
            
            order.save()
            return JsonResponse({'success': True, 'message': 'Вы успешно отменили участие в заказе'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': 'Ошибка при отмене заказа'}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Метод не поддерживается'}, status=405)

def user_logout(request):
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы')
    return redirect('main:auth')

@login_required
def add_portfolio(request):
    if request.method == 'POST':
        form = PortfolioForm(request.POST, request.FILES)
        files = request.FILES.getlist('photos')
        
        for f in files:
            Portfolio.objects.create(user=request.user, image=f)
            
        messages.success(request, 'Фотографии успешно добавлены в портфолио')
        return redirect('main:dashboard')
    
    return redirect('main:dashboard')

@login_required
def manage_tariff(request):
    if request.method == 'POST':
        tariff_id = request.POST.get('tariff_id')
        
        if tariff_id:
            # Edit existing tariff
            tariff = get_object_or_404(Tariff, id=tariff_id, user=request.user)
            form = TariffForm(request.POST, instance=tariff)
        else:
            # Create new tariff
            form = TariffForm(request.POST)
            
        if form.is_valid():
            tariff = form.save(commit=False)
            tariff.user = request.user
            tariff.save()
            messages.success(request, 'Тариф успешно сохранен')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме')
            
    return redirect('main:dashboard')

@login_required
def manage_calendar(request):
    if request.method == 'POST':
        dates = request.POST.get('selected_dates', '[]')
        try:
            dates = json.loads(dates)
            # Clear existing dates
            BusyDate.objects.filter(user=request.user).delete()
            # Add new dates
            for date_str in dates:
                # Parse date in user's timezone
                date = datetime.strptime(date_str, '%Y-%m-%d')
                # Convert to date object (removes time component)
                date = date.date()
                BusyDate.objects.create(user=request.user, date=date)
            messages.success(request, 'Календарь занятости обновлен')
        except json.JSONDecodeError:
            messages.error(request, 'Ошибка при обработке дат')
            
    return redirect('main:dashboard')

@login_required
def delete_portfolio_photo(request, photo_id):
    photo = get_object_or_404(Portfolio, id=photo_id, user=request.user)
    if request.method == 'POST':
        photo.delete()
        messages.success(request, 'Фото успешно удалено')
    return redirect('main:dashboard')

@login_required
def edit_tariff(request, tariff_id):
    tariff = get_object_or_404(Tariff, id=tariff_id, user=request.user)
    if request.method == 'POST':
        form = TariffForm(request.POST, instance=tariff)
        if form.is_valid():
            form.save()
            messages.success(request, 'Тариф успешно обновлен')
            return redirect('main:dashboard')
    
    # Return JSON response for AJAX request
    return JsonResponse({
        'id': tariff.id,
        'name': tariff.name,
        'price': str(tariff.price),
        'description': tariff.description or ''
    })

@login_required
def delete_tariff(request, tariff_id):
    tariff = get_object_or_404(Tariff, id=tariff_id, user=request.user)
    if request.method == 'POST':
        tariff.delete()
        messages.success(request, 'Тариф успешно удален')
    return redirect('main:dashboard')

@login_required
@require_GET
def get_chat_messages(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Проверяем права доступа
    if request.user != order.customer:
        # Для исполнителей проверяем, что они участвуют в заказе
        if order.selected_performers:
            # Для новых заказов с selected_performers
            is_performer = False
            for service, performer_id in order.selected_performers.items():
                if str(performer_id) == str(request.user.id):
                    is_performer = True
                    break
            if not is_performer:
                return JsonResponse({'error': 'Access denied'}, status=403)
        elif order.performer:
            # Для старых заказов
            if request.user != order.performer:
                return JsonResponse({'error': 'Access denied'}, status=403)
        else:
            return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Получаем все сообщения для заказа
    messages_qs = Message.objects.filter(order=order).order_by('created_at')
    
    # Mark messages as read
    messages_qs.filter(to_user=request.user, is_read=False).update(is_read=True)
    
    messages_data = [{
        'content': msg.content,
        'timestamp': msg.created_at.strftime('%H:%M'),
        'is_mine': msg.from_user == request.user
    } for msg in messages_qs]
    
    return JsonResponse({'messages': messages_data})

@login_required
@require_POST
def send_chat_message(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    data = json.loads(request.body)
    content = data.get('message', '').strip()
    if not content:
        return JsonResponse({'error': 'Message cannot be empty'}, status=400)
    
    # Определяем получателя сообщения
    if request.user == order.customer:
        # Заказчик отправляет сообщение исполнителю
        if order.selected_performers:
            # Для новых заказов с selected_performers
            for service, performer_id in order.selected_performers.items():
                performer = get_object_or_404(User, id=performer_id)
                break
        elif order.performer:
            # Для старых заказов
            performer = order.performer
        else:
            return JsonResponse({'error': 'No performer found for this order'}, status=400)
        to_user = performer
    elif request.user.user_type == 'performer':
        # Исполнитель отправляет сообщение заказчику
        to_user = order.customer
        performer = request.user
    else:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    Message.objects.create(
        order=order,
        from_user=request.user,
        to_user=to_user,
        content=content,
        performer=performer
    )
    return JsonResponse({'success': True})

@login_required
def get_user_orders(request):
    """Получение списка активных заявок пользователя для модального окна бронирования"""
    if request.user.user_type != 'customer':
        return JsonResponse({'error': 'Access denied'}, status=403)
        
    orders = Order.objects.filter(
        customer=request.user,
        status='new',
        order_type='request',
        performer__isnull=True  # Только заявки без исполнителя
    ).values('id', 'title', 'event_date')
    
    return JsonResponse({
        'orders': [{
            'id': order['id'],
            'title': order['title'],
            'event_date': order['event_date'].strftime('%d.%m.%Y') if order['event_date'] else ''
        } for order in orders]
    })

@login_required
def attach_performer_to_order(request, order_id, performer_id):
    """Создание предложения о бронировании"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    if request.user.user_type != 'customer':
        return JsonResponse({'error': 'Access denied'}, status=403)
        
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    performer = get_object_or_404(User, id=performer_id, user_type='performer')
    
    try:
        # Получаем данные из формы
        tariff_id = request.POST.get('tariff_id')
        date_str = request.POST.get('date')
        
        if not tariff_id or not date_str:
            return JsonResponse({'error': 'Missing required fields'}, status=400)
            
        tariff = get_object_or_404(Tariff, id=tariff_id, user=performer)
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Проверяем, нет ли уже предложения на эту дату
        if BookingProposal.objects.filter(
            performer=performer,
            date=date,
            status='pending'
        ).exists():
            return JsonResponse({
                'error': 'У исполнителя уже есть предложение на эту дату'
            }, status=400)
            
        # Создаем предложение о бронировании
        proposal = BookingProposal.objects.create(
            order=order,
            performer=performer,
            tariff=tariff,
            date=date,
            status='pending'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Предложение успешно отправлено'
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)

@csrf_exempt
def send_otp(request):
    print('send_otp called', request.method, request.POST)
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        if not phone_number:
            return JsonResponse({'error': 'Phone number is required'}, status=400)

        whatsapp_service = WhatsAppOTPService()
        otp_code = whatsapp_service.generate_otp()
        
        # Save OTP to database
        OTP.objects.create(
            phone_number=phone_number,
            code=otp_code
        )
        
        # Send OTP via WhatsApp
        if whatsapp_service.send_otp(phone_number, otp_code):
            return JsonResponse({'message': 'OTP sent successfully'})
        else:
            return JsonResponse({'error': 'Failed to send OTP'}, status=500)

@csrf_exempt
def verify_otp(request):
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        otp_code = request.POST.get('otp_code')
        
        if not phone_number or not otp_code:
            return JsonResponse({'error': 'Phone number and OTP code are required'}, status=400)
            
        # Get latest OTP for this phone number
        stored_otp = OTP.objects.filter(phone_number=phone_number).order_by('-created_at').first()
        
        if not stored_otp:
            return JsonResponse({'error': 'No OTP found for this phone number'}, status=400)
            
        whatsapp_service = WhatsAppOTPService()
        if whatsapp_service.verify_otp(phone_number, otp_code, stored_otp):
            # Check if user exists
            user = User.objects.filter(phone_number=phone_number).first()
            if user:
                user.is_phone_verified = True
                user.save()
                login(request, user)
                return JsonResponse({'message': 'OTP verified successfully', 'redirect': '/dashboard/'})
            else:
                # Store verified phone in session for registration
                request.session['verified_phone'] = phone_number
                return JsonResponse({'message': 'OTP verified successfully', 'redirect': '/register/'})
        else:
            return JsonResponse({'error': 'Invalid OTP'}, status=400)

@login_required
def update_profile_photo(request):
    """Handle profile photo upload"""
    if request.method == 'POST' and request.FILES.get('profile_photo'):
        user = request.user
        user.profile_photo = request.FILES['profile_photo']
        user.save()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'No photo provided'}, status=400)

@require_http_methods(["GET"])
def get_performer_busy_dates(request, performer_id):
    """API endpoint для получения занятых дат исполнителя"""
    try:
        performer = User.objects.get(id=performer_id, user_type='performer')
        busy_dates = BusyDate.objects.filter(user=performer).values_list('date', flat=True)
        
        # Также получаем даты из активных заказов (только in_progress)
        # Завершенные заказы (completed) не должны блокировать даты
        order_dates = Order.objects.filter(
            performer=performer,
            status='in_progress'
        ).values_list('event_date', flat=True)
        
        # Объединяем даты и убираем дубликаты
        all_busy_dates = set()
        for date in busy_dates:
            all_busy_dates.add(date.strftime('%Y-%m-%d'))
        for date in order_dates:
            if date:
                all_busy_dates.add(date.strftime('%Y-%m-%d'))
        
        return JsonResponse({
            'busy_dates': sorted(list(all_busy_dates))
        })
    except User.DoesNotExist:
        return JsonResponse({'error': 'Performer not found'}, status=404)

@require_http_methods(["GET"])
def get_performer_tariffs(request, performer_id):
    """API endpoint для получения тарифов исполнителя"""
    try:
        performer = User.objects.get(id=performer_id, user_type='performer')
        tariffs = Tariff.objects.filter(user=performer).values('id', 'name', 'price', 'description')
        return JsonResponse({
            'tariffs': list(tariffs)
        })
    except User.DoesNotExist:
        return JsonResponse({'error': 'Performer not found'}, status=404)

@login_required
@require_http_methods(["GET"])
def get_user_orders_api(request):
    """API для получения заявок пользователя"""
    try:
        orders = Order.objects.filter(customer=request.user).order_by('-created_at')
        
        orders_data = []
        for order in orders:
            orders_data.append({
                'id': order.id,
                'title': order.title,
                'event_date': order.event_date.strftime('%d.%m.%Y') if order.event_date else '',
                'status': order.status,
                'budget_min': str(order.budget_min) if order.budget_min else '0',
                'budget_max': str(order.budget_max) if order.budget_max else '0',
                'city': order.city or '',
                'description': order.description or ''
            })
        
        return JsonResponse({
            'success': True,
            'orders': orders_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def accept_proposal(request, proposal_id):
    if request.method == 'POST' and request.user.user_type == 'performer':
        proposal = get_object_or_404(BookingProposal, id=proposal_id, performer=request.user)
        
        if proposal.status == 'pending':
            try:
                # Создаем новый заказ или обновляем существующий
                order = proposal.order
                order.performer = request.user
                order.status = 'in_progress'
                order.save()
                
                # Добавляем дату в занятые
                BusyDate.objects.create(
                    user=request.user,
                    date=proposal.date
                )
                
                # Обновляем статус предложения
                proposal.status = 'accepted'
                proposal.save()
                
                messages.success(request, 'Предложение успешно принято')
            except Exception as e:
                messages.error(request, 'Произошла ошибка при принятии предложения')
        else:
            messages.error(request, 'Это предложение уже не доступно')
            
    return redirect('main:dashboard')

@login_required
def reject_proposal(request, proposal_id):
    if request.method == 'POST' and request.user.user_type == 'performer':
        proposal = get_object_or_404(BookingProposal, id=proposal_id, performer=request.user)
        
        if proposal.status == 'pending':
            try:
                # Обновляем статус предложения
                proposal.status = 'rejected'
                proposal.save()
                
                messages.success(request, 'Предложение отклонено')
            except Exception as e:
                messages.error(request, 'Произошла ошибка при отклонении предложения')
        else:
            messages.error(request, 'Это предложение уже не доступно')
            
    return redirect('main:dashboard')

@login_required
def order_detail_api(request, order_id):
    """API для получения данных заявки для модального окна"""
    order = get_object_or_404(Order, id=order_id)
    
    # Проверяем права доступа
    if request.user.user_type == 'performer':
        # Исполнители могут видеть все заявки
        pass
    elif request.user == order.customer:
        # Заказчики могут видеть свои заявки
        pass
    else:
        return JsonResponse({'success': False, 'error': 'Доступ запрещен'}, status=403)
    
    # Проверяем, является ли пользователь выбранным исполнителем
    is_selected_performer = False
    if request.user.user_type == 'performer':
        if order.order_type == 'booking' and order.performer == request.user:
            is_selected_performer = True
        elif order.order_type == 'request' and order.selected_performers:
            selected = order.selected_performers or {}
            service_type_code = request.user.service_type.code if request.user.service_type else None
            if service_type_code in selected and str(selected[service_type_code]) == str(request.user.id):
                is_selected_performer = True
    
    # Подготавливаем данные для JSON
    order_data = {
        'id': order.id,
        'title': order.title,
        'event_type': order.event_type,
        'event_date': order.event_date.strftime('%d.%m.%Y') if order.event_date else None,
        'city': order.city,
        'venue': order.venue,
        'guest_count': order.guest_count,
        'budget_min': str(order.budget_min),
        'budget_max': str(order.budget_max),
        'description': order.description,
        'status': order.status,
        'order_type': order.order_type,
        'services': order.services,
        'is_selected_performer': is_selected_performer,
        'is_customer': request.user == order.customer,  # Добавляем информацию о том, является ли пользователь заказчиком
        'is_performer': request.user == order.performer,  # Добавляем информацию о том, является ли пользователь исполнителем
        'customer': {
            'name': order.customer.get_full_name(),
            'city': order.customer.city.name if order.customer.city else None,
        } if order.customer else None
    }
    
    print(f"DEBUG: is_customer = {request.user == order.customer}")  # Отладочная информация
    print(f"DEBUG: request.user = {request.user.id}, order.customer = {order.customer.id}")  # Отладочная информация
    
    return JsonResponse({
        'success': True,
        'order': order_data
    })

@login_required
@require_POST
def order_respond_api(request, order_id):
    """API для отправки отклика на заявку"""
    order = get_object_or_404(Order, id=order_id)
    
    # Проверяем, что пользователь - исполнитель
    if request.user.user_type != 'performer':
        return JsonResponse({'success': False, 'error': 'Только исполнители могут откликаться на заявки'}, status=403)
    
    # Проверяем, что заявка доступна для отклика
    if order.status != 'new' or order.order_type != 'request':
        return JsonResponse({'success': False, 'error': 'Заявка недоступна для отклика'}, status=400)
    
    try:
        data = json.loads(request.body)
        price = data.get('price')
        message = data.get('message', '')
        
        if not price:
            return JsonResponse({'success': False, 'error': 'Не указана цена'}, status=400)
        
        # Создаем отклик
        OrderResponse.objects.create(
            order=order,
            performer=request.user,
            price=Decimal(price),
            message=message
        )
        
        return JsonResponse({'success': True})
        
    except (ValueError, TypeError) as e:
        return JsonResponse({'success': False, 'error': 'Неверные данные'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'Ошибка сервера'}, status=500)

@login_required
@require_POST
def accept_response(request, response_id):
    """Принятие отклика заказчиком"""
    try:
        response = get_object_or_404(OrderResponse, id=response_id)
        order = response.order
        
        # Проверяем, что пользователь является заказчиком этого заказа
        if request.user != order.customer:
            return JsonResponse({'error': 'У вас нет прав для принятия этого отклика'}, status=403)
        
        # Проверяем, что заказ еще новый
        if order.status != 'new':
            return JsonResponse({'error': 'Заказ уже не доступен для принятия откликов'}, status=400)
        
        # Проверяем, что исполнитель не выбран по этой услуге
        service_type = response.performer.service_type.code if response.performer.service_type else None
        if not service_type:
            return JsonResponse({'error': 'У исполнителя не указан тип услуги'}, status=400)
        
        selected_performers = order.selected_performers or {}
        if service_type in selected_performers:
            return JsonResponse({'error': 'Исполнитель по этой услуге уже выбран'}, status=400)
        
        # Принимаем отклик
        selected_performers[service_type] = response.performer.id
        order.selected_performers = selected_performers
        
        # Устанавливаем исполнителя для заказа (берем первого из выбранных)
        if not order.performer:
            order.performer = response.performer
        
        # Проверяем, выбраны ли все необходимые услуги
        if set(selected_performers.keys()) == set(order.services):
            order.status = 'in_progress'
        
        order.save()
        
        # Удаляем все остальные отклики по этой услуге
        OrderResponse.objects.filter(
            order=order, 
            performer__service_type__code=service_type
        ).exclude(id=response_id).delete()
        
        # Создаем первое сообщение в чате
        Message.objects.create(
            order=order,
            from_user=request.user,
            to_user=response.performer,
            content=f'Здравствуйте! Я выбрал вас для выполнения услуги "{service_type}". Давайте обсудим детали.',
            performer=response.performer
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Исполнитель по услуге {service_type} успешно выбран'
        })
        
    except Exception as e:
        return JsonResponse({'error': 'Произошла ошибка при принятии отклика'}, status=500)

@login_required
@require_POST
def reject_response(request, response_id):
    """Отклонение отклика заказчиком"""
    try:
        response = get_object_or_404(OrderResponse, id=response_id)
        order = response.order
        
        # Проверяем, что пользователь является заказчиком этого заказа
        if request.user != order.customer:
            return JsonResponse({'error': 'У вас нет прав для отклонения этого отклика'}, status=403)
        
        # Удаляем отклик
        response.delete()
        
        # Если заказ был в работе и теперь нет откликов, возвращаем статус 'new'
        if order.status == 'in_progress':
            remaining_responses = OrderResponse.objects.filter(order=order).count()
            if remaining_responses == 0:
                # Очищаем выбранных исполнителей и возвращаем статус 'new'
                order.selected_performers = {}
                order.performer = None  # Очищаем исполнителя
                order.status = 'new'
                order.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Отклик отклонен'
        })
        
    except Exception as e:
        return JsonResponse({'error': 'Произошла ошибка при отклонении отклика'}, status=500)

@login_required
@require_POST
def cancel_order_api(request, order_id):
    """API для отмены заказа"""
    try:
        order = Order.objects.get(id=order_id)
        
        # Проверяем права доступа
        if request.user != order.customer and request.user != order.performer:
            return JsonResponse({'success': False, 'error': 'Нет прав для отмены этого заказа'})
        
        # Проверяем, что заказ не завершен
        if order.status == 'completed':
            return JsonResponse({'success': False, 'error': 'Нельзя отменить завершенный заказ'})
        
        # Если заказ в работе, удаляем связанные данные и возвращаем статус 'new'
        if order.status == 'in_progress':
            # Удаляем отклики исполнителей
            OrderResponse.objects.filter(order=order).delete()
            
            # Удаляем занятые даты исполнителей при отмене заказа
            if order.performer:
                BusyDate.objects.filter(user=order.performer, date=order.event_date).delete()
            
            # Очищаем выбранных исполнителей и возвращаем статус 'new'
            order.selected_performers = {}
            order.status = 'new'
            order.save()
            
            return JsonResponse({'success': True, 'message': 'Заказ возвращен в активное состояние'})
        
        # Если заказ новый, отменяем его
        order.status = 'cancelled'
        order.save()
        
        return JsonResponse({'success': True, 'message': 'Заказ успешно отменен'})
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Заказ не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def complete_order_api(request, order_id):
    """API для завершения заказа"""
    try:
        order = Order.objects.get(id=order_id)
        
        # Определяем исполнителя заказа
        performer = order.performer
        if not performer and order.selected_performers:
            # Если performer не установлен, берем первого из selected_performers
            first_performer_id = list(order.selected_performers.values())[0]
            performer = User.objects.get(id=first_performer_id)
        
        # Проверяем, что это исполнитель или заказчик заказа
        if request.user not in [performer, order.customer]:
            return JsonResponse({'success': False, 'error': 'Только участники заказа могут завершить заказ'})
        
        # Проверяем, что заказ в работе
        if order.status != 'in_progress':
            return JsonResponse({'success': False, 'error': 'Можно завершить только заказ в работе'})
        
        # Завершаем заказ
        order.status = 'completed'
        order.save()
        
        # Освобождаем дату из занятых дат исполнителя при завершении заказа
        from datetime import date
        if performer and order.event_date >= date.today():
            from main.models import BusyDate
            BusyDate.objects.filter(
                user=performer, 
                date=order.event_date
            ).delete()
        
        return JsonResponse({'success': True, 'message': 'Заказ успешно завершен'})
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Заказ не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def create_review_api(request, order_id):
    """API для создания отзыва заказчиком"""
    try:
        order = Order.objects.get(id=order_id)
        
        # Проверяем, что это заказчик заказа
        if request.user != order.customer:
            return JsonResponse({'success': False, 'error': 'Только заказчик может оставить отзыв'})
        
        # Проверяем, что заказ завершен
        if order.status != 'completed':
            return JsonResponse({'success': False, 'error': 'Отзыв можно оставить только для завершенного заказа'})
        
        # Проверяем, что у заказа есть исполнитель
        if not order.performer:
            return JsonResponse({'success': False, 'error': 'Нельзя оставить отзыв для заказа без исполнителя'})
        
        # Проверяем, что отзыв еще не оставлен
        if Review.objects.filter(order=order, from_user=request.user).exists():
            return JsonResponse({'success': False, 'error': 'Отзыв уже оставлен для этого заказа'})
        
        # Получаем данные отзыва
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()
        
        if not rating or not rating.isdigit() or int(rating) < 1 or int(rating) > 5:
            return JsonResponse({'success': False, 'error': 'Неверная оценка'})
        
        if not comment:
            return JsonResponse({'success': False, 'error': 'Комментарий обязателен'})
        
        # Создаем отзыв
        review = Review.objects.create(
            order=order,
            from_user=request.user,
            to_user=order.performer,
            rating=int(rating),
            comment=comment
        )
        
        # Обновляем рейтинг исполнителя
        performer = order.performer
        avg_rating = Review.objects.filter(to_user=performer).aggregate(
            avg_rating=models.Avg('rating')
        )['avg_rating'] or 0
        performer.rating = round(avg_rating, 1)
        performer.save()
        
        return JsonResponse({'success': True, 'message': 'Отзыв успешно добавлен'})
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Заказ не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def performer_cancel_booking_api(request, order_id):
    """API для отмены бронирования исполнителем"""
    try:
        order = Order.objects.get(id=order_id)
        
        # Проверяем, что это исполнитель заказа
        if request.user != order.performer:
            return JsonResponse({'success': False, 'error': 'Только исполнитель может отменить бронирование'})
        
        # Проверяем, что это бронирование
        if order.order_type != 'booking':
            return JsonResponse({'success': False, 'error': 'Это не бронирование'})
        
        # Проверяем, что заказ еще не в работе
        if order.status != 'new':
            return JsonResponse({'success': False, 'error': 'Нельзя отменить заказ в работе'})
        
        # Отменяем заказ
        order.status = 'cancelled'
        order.save()
        
        # Освобождаем дату из занятых дат исполнителя
        from main.models import BusyDate
        BusyDate.objects.filter(
            user=order.performer, 
            date=order.event_date
        ).delete()
        
        return JsonResponse({'success': True, 'message': 'Бронирование успешно отменено'})
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Заказ не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def delete_order_api(request, order_id):
    """API для удаления заказа"""
    try:
        order = Order.objects.get(id=order_id)
        
        # Проверяем, что это заказчик заказа
        if request.user != order.customer:
            return JsonResponse({'success': False, 'error': 'Только заказчик может удалить заказ'})
        
        # Проверяем, что заказ еще не в работе
        if order.status != 'new':
            return JsonResponse({'success': False, 'error': 'Нельзя удалить заказ в работе'})
        
        # Удаляем заказ
        order.delete()
        
        return JsonResponse({'success': True, 'message': 'Заказ успешно удален'})
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Заказ не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def performer_cancel_booking_api(request, order_id):
    """API для отмены бронирования исполнителем"""
    try:
        order = Order.objects.get(id=order_id)
        
        # Проверяем, что это исполнитель заказа
        if request.user != order.performer:
            return JsonResponse({'success': False, 'error': 'Только исполнитель может отменить бронирование'})
        
        # Проверяем, что это бронирование
        if order.order_type != 'booking':
            return JsonResponse({'success': False, 'error': 'Это не бронирование'})
        
        # Проверяем, что заказ еще не в работе
        if order.status != 'new':
            return JsonResponse({'success': False, 'error': 'Нельзя отменить заказ в работе'})
        
        # Отменяем заказ
        order.status = 'cancelled'
        order.save()
        
        # Освобождаем дату из занятых дат исполнителя
        from main.models import BusyDate
        BusyDate.objects.filter(
            user=order.performer, 
            date=order.event_date
        ).delete()
        
        return JsonResponse({'success': True, 'message': 'Бронирование успешно отменено'})
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Заказ не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def accept_booking_api(request, order_id):
    """API для принятия бронирования исполнителем"""
    try:
        order = Order.objects.get(id=order_id)
        
        # Проверяем, что это исполнитель заказа
        if request.user != order.performer:
            return JsonResponse({'success': False, 'error': 'Только исполнитель может принять бронирование'})
        
        # Проверяем, что это бронирование
        if order.order_type != 'booking':
            return JsonResponse({'success': False, 'error': 'Это не бронирование'})
        
        # Проверяем, что заказ еще новый
        if order.status != 'new':
            return JsonResponse({'success': False, 'error': 'Нельзя принять заказ в работе'})
        
        # Принимаем бронирование
        order.status = 'in_progress'
        order.save()
        
        return JsonResponse({'success': True, 'message': 'Бронирование успешно принято'})
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Заказ не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def reject_booking_api(request, order_id):
    """API для отклонения бронирования исполнителем"""
    try:
        order = Order.objects.get(id=order_id)
        
        # Проверяем, что это исполнитель заказа
        if request.user != order.performer:
            return JsonResponse({'success': False, 'error': 'Только исполнитель может отклонить бронирование'})
        
        # Проверяем, что это бронирование
        if order.order_type != 'booking':
            return JsonResponse({'success': False, 'error': 'Это не бронирование'})
        
        # Проверяем, что заказ еще новый
        if order.status != 'new':
            return JsonResponse({'success': False, 'error': 'Нельзя отклонить заказ в работе'})
        
        # Отклоняем бронирование
        order.status = 'cancelled'
        order.save()
        
        # Освобождаем дату из занятых дат исполнителя
        from main.models import BusyDate
        BusyDate.objects.filter(
            user=order.performer, 
            date=order.event_date
        ).delete()
        
        return JsonResponse({'success': True, 'message': 'Бронирование отклонено'})
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Заказ не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def delete_order_api(request, order_id):
    """API для удаления заказа"""
    try:
        order = Order.objects.get(id=order_id)
        
        # Проверяем, что это заказчик заказа
        if request.user != order.customer:
            return JsonResponse({'success': False, 'error': 'Только заказчик может удалить заказ'})
        
        # Проверяем, что заказ еще не в работе
        if order.status != 'new':
            return JsonResponse({'success': False, 'error': 'Нельзя удалить заказ в работе'})
        
        # Удаляем заказ
        order.delete()
        
        return JsonResponse({'success': True, 'message': 'Заказ успешно удален'})
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Заказ не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def cancel_response(request, response_id):
    """Отмена отклика исполнителем"""
    try:
        response = get_object_or_404(OrderResponse, id=response_id)
        order = response.order
        
        # Проверяем, что пользователь является исполнителем этого отклика
        if request.user != response.performer:
            return JsonResponse({'error': 'У вас нет прав для отмены этого отклика'}, status=403)
        
        # Удаляем отклик
        response.delete()
        
        # Если заказ был в работе и теперь нет откликов, возвращаем статус 'new'
        if order.status == 'in_progress':
            remaining_responses = OrderResponse.objects.filter(order=order).count()
            if remaining_responses == 0:
                # Очищаем выбранных исполнителей и возвращаем статус 'new'
                order.selected_performers = {}
                order.status = 'new'
                order.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Отклик успешно отменен'
        })
        
    except Exception as e:
        return JsonResponse({'error': 'Произошла ошибка при отмене отклика'}, status=500)

def cleanup_past_busy_dates():
    """Очищает занятые даты, которые уже прошли"""
    today = date.today()
    
    # Удаляем занятые даты, которые уже прошли
    BusyDate.objects.filter(date__lt=today).delete()

def test_mobile(request):
    """Тестовая страница для проверки мобильного меню"""
    return render(request, 'test_mobile.html')
