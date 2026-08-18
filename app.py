from flask import Flask, render_template, request
from database import get_db_connection
from pricing import calculate_price

from datetime import date
import random
import string


app = Flask(__name__)


# =====================================================
# HOME
# =====================================================

@app.route("/")
def home():
    return render_template("index.html")


# =====================================================
# SHOW CRUISES
# =====================================================

@app.route("/cruises")
def cruises():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT
            c.cruise_id,
            c.cruise_line,
            c.ship_name,
            c.destination,

            d.departure_id,
            d.departure_date,
            d.return_date,
            d.nights,
            d.adult_fare,
            d.capacity,
            d.capacity_left

        FROM cruises c

        JOIN cruise_departures d
            ON c.cruise_id = d.cruise_id

        WHERE d.capacity_left > 0

        ORDER BY d.departure_date
    """

    cursor.execute(query)

    cruises_data = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "cruises.html",
        cruises=cruises_data
    )


# =====================================================
# BOOKING
# =====================================================

@app.route(
    "/book/<int:departure_id>",
    methods=["GET", "POST"]
)
def book(departure_id):

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # -------------------------------------------------
    # Get cruise departure
    # -------------------------------------------------

    cursor.execute(
        """
        SELECT
            cd.*,
            c.cruise_line,
            c.ship_name,
            c.destination

        FROM cruise_departures cd

        JOIN cruises c
            ON cd.cruise_id = c.cruise_id

        WHERE cd.departure_id = %s
        """,
        (departure_id,)
    )

    cruise = cursor.fetchone()

    if not cruise:

        cursor.close()
        connection.close()

        return "Cruise departure not found", 404


    # -------------------------------------------------
    # Get services
    # -------------------------------------------------

    cursor.execute(
        """
        SELECT *
        FROM optional_services
        """
    )

    services = cursor.fetchall()


    # -------------------------------------------------
    # Get active promotions
    # -------------------------------------------------

    cursor.execute(
        """
        SELECT *
        FROM promotional_codes
        WHERE active = TRUE
        """
    )

    promotions = cursor.fetchall()


    # =================================================
    # GET
    # =================================================

    if request.method == "GET":

        cursor.close()
        connection.close()

        return render_template(
            "booking.html",
            cruise=cruise,
            services=services,
            promotions=promotions
        )


    # =================================================
    # POST
    # =================================================

    customer_name = request.form.get(
        "customer_name",
        ""
    ).strip()

    customer_email = request.form.get(
        "customer_email",
        ""
    ).strip()

    customer_phone = request.form.get(
        "customer_phone",
        ""
    ).strip()


    if not customer_name or not customer_email:

        cursor.close()
        connection.close()

        return "Customer name and email are required."


    # -------------------------------------------------
    # Passenger ages
    # -------------------------------------------------

    passenger_ages = []

    for i in range(1, 7):

        age = request.form.get(
            f"age_{i}"
        )

        if age:

            try:
                age = int(age)
            except ValueError:

                cursor.close()
                connection.close()

                return "Invalid passenger age."

            if age < 0:

                cursor.close()
                connection.close()

                return "Age cannot be negative."

            passenger_ages.append(age)


    if len(passenger_ages) == 0:

        cursor.close()
        connection.close()

        return "At least one passenger is required."


    if len(passenger_ages) > 6:

        cursor.close()
        connection.close()

        return "Maximum 6 passengers allowed."


    # -------------------------------------------------
    # Passenger count
    # -------------------------------------------------

    total_passengers = len(passenger_ages)

    adult_count = sum(
        1
        for age in passenger_ages
        if age >= 18
    )

    child_count = (
        total_passengers - adult_count
    )


    # -------------------------------------------------
    # Capacity
    # -------------------------------------------------

    if total_passengers > cruise["capacity_left"]:

        cursor.close()
        connection.close()

        return (
            f"Only {cruise['capacity_left']} "
            f"passengers are available."
        )


    # -------------------------------------------------
    # Services
    # -------------------------------------------------

    selected_service_ids = request.form.getlist(
        "services"
    )

    selected_services = []

    if selected_service_ids:

        placeholders = ",".join(
            ["%s"] * len(selected_service_ids)
        )

        cursor.execute(
            f"""
            SELECT *
            FROM optional_services
            WHERE service_id IN ({placeholders})
            """,
            tuple(selected_service_ids)
        )

        selected_services = cursor.fetchall()


    # -------------------------------------------------
    # Promotion
    # -------------------------------------------------

    promotion = None
    promotion_error = None

    promotion_code = request.form.get(
        "promotion_code",
        ""
    ).strip().upper()


    if promotion_code:

        cursor.execute(
            """
            SELECT *
            FROM promotional_codes
            WHERE code = %s
            AND active = TRUE
            """,
            (promotion_code,)
        )

        promotion = cursor.fetchone()


        if not promotion:

            promotion_error = (
                "Invalid promotional code."
            )

        else:

            today = date.today()

            if (
                today < promotion["valid_from"]
                or
                today > promotion["valid_until"]
            ):

                promotion_error = (
                    "Promotional code is outside "
                    "its valid date range."
                )

                promotion = None


    if promotion_error:

        cursor.close()
        connection.close()

        return render_template(
            "booking.html",
            cruise=cruise,
            services=services,
            promotions=promotions,
            error=promotion_error
        )


    # =================================================
    # CALCULATE PRICE
    # =================================================

    price = calculate_price(
        cruise["adult_fare"],
        cruise["nights"],
        passenger_ages,
        selected_services,
        promotion
    )


    # =================================================
    # SAVE CUSTOMER
    # =================================================

    cursor.execute(
        """
        INSERT INTO customers
        (
            name,
            email,
            phone
        )

        VALUES
        (%s, %s, %s)
        """,
        (
            customer_name,
            customer_email,
            customer_phone
        )
    )

    customer_id = cursor.lastrowid


    # =================================================
    # BOOKING REFERENCE
    # =================================================

    reference = generate_reference()


    # =================================================
    # PROMOTION
    # =================================================

    promotion_id = (
        promotion["promotion_id"]
        if promotion
        else None
    )


    # =================================================
    # SAVE ORDER
    # =================================================

    cursor.execute(
        """
        INSERT INTO orders
        (
            order_reference,
            customer_id,
            departure_id,

            adult_count,
            child_count,
            total_passengers,

            base_fare,
            group_discount,
            promotion_discount,
            services_total,

            subtotal,
            tax_rate,
            tax_amount,
            final_amount,

            promotion_id
        )

        VALUES
        (
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s
        )
        """,
        (
            reference,
            customer_id,
            departure_id,

            adult_count,
            child_count,
            total_passengers,

            price["base_fare"],
            price["group_discount"],
            price["promotion_discount"],
            price["services_total"],

            price["subtotal"],
            price["tax_rate"],
            price["tax_amount"],
            price["final_amount"],

            promotion_id
        )
    )

    order_id = cursor.lastrowid


    # =================================================
    # SAVE PASSENGERS
    # =================================================

    for index, passenger in enumerate(
        price["passenger_fares"],
        start=1
    ):

        age = passenger["age"]

        cursor.execute(
            """
            INSERT INTO passengers
            (
                order_id,
                passenger_number,
                name,
                age,
                fare_percentage,
                fare_amount
            )

            VALUES
            (%s, %s, %s, %s, %s, %s)
            """,
            (
                order_id,
                index,
                f"Passenger {index}",
                age,
                passenger["percentage"],
                passenger["fare"]
            )
        )


    # =================================================
    # SAVE SERVICES
    # =================================================

    for service in price["service_details"]:

        cursor.execute(
            """
            INSERT INTO order_services
            (
                order_id,
                service_id,
                quantity,
                unit_price,
                total_price
            )

            VALUES
            (%s, %s, %s, %s, %s)
            """,
            (
                order_id,
                service["service_id"],
                service["quantity"],
                service["unit_price"],
                service["total"]
            )
        )


    # =================================================
    # PROMOTION REDEMPTION
    # =================================================

    if promotion:

        # Check customer usage
        cursor.execute(
            """
            SELECT COUNT(*) AS usage_count

            FROM promotion_redemptions

            WHERE promotion_id = %s
            AND customer_id = %s
            """,
            (
                promotion["promotion_id"],
                customer_id
            )
        )

        usage = cursor.fetchone()


        max_uses = promotion[
            "max_uses_per_customer"
        ]


        if (
            max_uses is not None
            and
            usage["usage_count"] >= max_uses
        ):

            connection.rollback()

            cursor.close()
            connection.close()

            return (
                "You have reached the maximum "
                "usage limit for this promotion."
            )


        # Check total usage
        max_total = promotion[
            "max_total_uses"
        ]

        if max_total is not None:

            cursor.execute(
                """
                SELECT COUNT(*) AS total_usage

                FROM promotion_redemptions

                WHERE promotion_id = %s
                """,
                (
                    promotion["promotion_id"],
                )
            )

            total_usage = cursor.fetchone()


            if total_usage["total_usage"] >= max_total:

                connection.rollback()

                cursor.close()
                connection.close()

                return (
                    "This promotional code has "
                    "reached its total usage limit."
                )


        cursor.execute(
            """
            INSERT INTO promotion_redemptions
            (
                promotion_id,
                customer_id,
                order_id
            )

            VALUES
            (%s, %s, %s)
            """,
            (
                promotion["promotion_id"],
                customer_id,
                order_id
            )
        )


    # =================================================
    # HISTORICAL PRICE SNAPSHOT
    # =================================================

    cursor.execute(
        """
        INSERT INTO order_pricing
        (
            order_id,

            base_fare,

            group_discount_rate,
            group_discount_amount,

            promotion_discount_amount,

            services_total,

            subtotal,

            tax_rate,
            tax_amount,

            final_amount
        )

        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            order_id,

            price["base_fare"],

            price["group_rate"],
            price["group_discount"],

            price["promotion_discount"],

            price["services_total"],

            price["subtotal"],

            price["tax_rate"],
            price["tax_amount"],

            price["final_amount"]
        )
    )


    # =================================================
    # CONFIRM BOOKING
    # =================================================

    cursor.execute(
        """
        UPDATE orders

        SET status = 'CONFIRMED'

        WHERE order_id = %s
        """,
        (order_id,)
    )


    # =================================================
    # UPDATE CAPACITY
    # =================================================

    cursor.execute(
        """
        UPDATE cruise_departures

        SET capacity_left =
            capacity_left - %s

        WHERE departure_id = %s
        AND capacity_left >= %s
        """,
        (
            total_passengers,
            departure_id,
            total_passengers
        )
    )


    if cursor.rowcount != 1:

        connection.rollback()

        cursor.close()
        connection.close()

        return (
            "Booking failed because there is "
            "not enough capacity."
        )


    # =================================================
    # COMMIT
    # =================================================

    connection.commit()

    cursor.close()
    connection.close()


    # =================================================
    # CONFIRMATION
    # =================================================

    return render_template(
        "confirmation.html",
        reference=reference,
        price=price,
        cruise=cruise,
        customer_name=customer_name
    )


# =====================================================
# BOOKINGS
# =====================================================

@app.route("/bookings")
def bookings():

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            o.order_reference,

            c.name AS customer_name,

            cr.ship_name,

            cr.destination,

            cd.departure_date,

            o.total_passengers,

            o.final_amount,

            o.status

        FROM orders o

        JOIN customers c
            ON o.customer_id = c.customer_id

        JOIN cruise_departures cd
            ON o.departure_id = cd.departure_id

        JOIN cruises cr
            ON cd.cruise_id = cr.cruise_id

        ORDER BY o.created_at DESC
        """
    )

    data = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "bookings.html",
        bookings=data
    )


# =====================================================
# REFERENCE GENERATOR
# =====================================================

def generate_reference():

    characters = (
        string.ascii_uppercase
        + string.digits
    )

    random_part = "".join(
        random.choices(
            characters,
            k=8
        )
    )

    return "CRZ-" + random_part


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )