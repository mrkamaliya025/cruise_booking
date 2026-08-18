from decimal import Decimal, ROUND_HALF_UP


TAX_RATE = Decimal("0.12")


def money(value):
    """
    Convert a value to Decimal with 2 decimal places.
    """
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def get_passenger_fare_percentage(age):

    if age <= 4:
        return Decimal("0")

    elif age <= 11:
        return Decimal("0.50")

    elif age <= 17:
        return Decimal("0.70")

    else:
        return Decimal("1.00")


def get_group_discount_rate(total_passengers):

    if total_passengers <= 2:
        return Decimal("0")

    elif total_passengers <= 4:
        return Decimal("0.05")

    else:
        return Decimal("0.10")


def calculate_price(
    adult_fare,
    nights,
    passenger_ages,
    services,
    promotion=None
):

    # Convert adult fare to Decimal
    adult_fare = money(adult_fare)

    total_passengers = len(passenger_ages)

    # ----------------------------------
    # Passenger limit
    # ----------------------------------

    if total_passengers < 1:
        raise ValueError(
            "At least one passenger is required."
        )

    if total_passengers > 6:
        raise ValueError(
            "Maximum 6 passengers allowed."
        )

    # ----------------------------------
    # Passenger fares
    # ----------------------------------

    passenger_fares = []

    base_fare = Decimal("0")

    for age in passenger_ages:

        percentage = get_passenger_fare_percentage(age)

        fare = adult_fare * percentage

        fare = money(fare)

        passenger_fares.append({
            "age": age,
            "percentage": percentage * 100,
            "fare": fare
        })

        base_fare += fare

    base_fare = money(base_fare)

    # ----------------------------------
    # Group discount
    # ----------------------------------

    group_rate = get_group_discount_rate(
        total_passengers
    )

    group_discount = money(
        base_fare * group_rate
    )

    after_group_discount = (
        base_fare - group_discount
    )

    # ----------------------------------
    # Promotion
    # ----------------------------------

    promotion_discount = Decimal("0")

    if promotion:

        discount_value = Decimal(
            str(promotion["discount_value"])
        )

        if promotion["discount_type"] == "PERCENTAGE":

            promotion_discount = money(
                after_group_discount
                * discount_value
                / Decimal("100")
            )

        elif promotion["discount_type"] == "FIXED":

            promotion_discount = money(
                discount_value
            )

            # Never allow total to become negative
            promotion_discount = min(
                promotion_discount,
                after_group_discount
            )

    after_promotion = (
        after_group_discount
        - promotion_discount
    )

    # ----------------------------------
    # Optional services
    # ----------------------------------

    services_total = Decimal("0")

    service_details = []

    for service in services:

        service_price = money(
            service["price"]
        )

        if service["pricing_type"] == "PER_PASSENGER":

            quantity = total_passengers

        elif service["pricing_type"] == "PER_PASSENGER_NIGHT":

            quantity = (
                total_passengers * nights
            )

        else:

            quantity = 0

        total = money(
            service_price * quantity
        )

        services_total += total

        service_details.append({
            "service_id": service["service_id"],
            "name": service["name"],
            "quantity": quantity,
            "unit_price": service_price,
            "total": total
        })

    services_total = money(
        services_total
    )

    # ----------------------------------
    # Subtotal
    # ----------------------------------

    subtotal = money(
        after_promotion + services_total
    )

    # ----------------------------------
    # Tax
    # ----------------------------------

    tax_amount = money(
        subtotal * TAX_RATE
    )

    # ----------------------------------
    # Final amount
    # ----------------------------------

    final_amount = money(
        subtotal + tax_amount
    )

    # ----------------------------------
    # Return result
    # ----------------------------------

    return {

        "passenger_fares": passenger_fares,

        "base_fare": base_fare,

        "group_rate": group_rate * 100,

        "group_discount": group_discount,

        "promotion_discount": promotion_discount,

        "services_total": services_total,

        "service_details": service_details,

        "subtotal": subtotal,

        "tax_rate": TAX_RATE * 100,

        "tax_amount": tax_amount,

        "final_amount": final_amount
    }