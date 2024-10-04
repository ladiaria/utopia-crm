import logging
from tqdm import tqdm

from core.models import Contact, Subscription
from advertisement.models import Agency, Advertiser
from logistics.models import Route


phone_fields = {
    Contact: ["phone", "work_phone", "mobile"],
    Subscription: ["billing_phone"],
    Agency: ["phone", "billing_phone"],
    Advertiser: ["phone", "billing_phone"],
    Route: ["phone", "mobile"],
}
extension_fields = {
    Contact: ["phone", "work_phone"],
    Subscription: ["billing_phone"],
    Route: ["phone"],
}


def sql_replacements():
    blank_patterns = ['-+', '0+']
    with open('/tmp/normalize_phone_numbers.sql', 'w') as f:
        for model, fields in phone_fields.items():
            for field in fields:
                where = ' OR '.join([f"{field} ~ '^{pattern}$'" for pattern in blank_patterns])
                f.write(f"UPDATE {model._meta.db_table} SET {field} = '' WHERE {where};\n")
        for model, fields in extension_fields.items():
            for field in fields:
                set_str = f"{field}=trim(both ' ' FROM split_part({field}, '/', 1)),"
                set_str += f"{field}_extension=trim(both ' ' FROM split_part({field}, '/', 2))"
                f.write(f"UPDATE {model._meta.db_table} SET {set_str} WHERE {field} LIKE '%/%';\n")


def normalize_phone_numbers(exclude=[], filters={}, dry_run=False):
    logging.basicConfig(
        filename='/tmp/normalize_phone_numbers.log',
        level=logging.INFO,
        filemode='w',
        format='%(levelname)s: %(message)s',
    )
    models_to_normalize = [m for m in phone_fields.keys() if m.__name__ not in exclude]

    for model in models_to_normalize:
        model_name, model_objects = model.__name__, model.objects

        filter = filters.get(model_name)
        if filter:
            model_objects = model_objects.filter(**filter)

        model_objects = model_objects.exclude(**{f: "" for f in phone_fields.get(model, [])})

        saved, already_normalized_with_invalid, already_normalized_no_invalid = 0, 0, 0
        with_all_invalid, with_error, total = 0, 0, model_objects.count()
        if total:
            logging.info(f"{model_name} objects to normalize: {total}")
        else:
            continue

        for obj in tqdm(model_objects.iterator(), total=total, desc=f"Normalizing {model_name}"):

            need_save = False
            has_valid = False
            invalids = []

            for field in phone_fields.get(model, []):
                value = getattr(obj, field)
                if value:
                    if value.is_valid():
                        has_valid = True
                        need_save = need_save or value.raw_input != value.as_e164
                    else:
                        invalids.append((field, value))

            has_invalid = bool(invalids)
            if has_invalid:
                invalids_str = ", ".join([f"{field}: {value}" for field, value in invalids])
                logging.warning(f"Invalid numbers for {model_name} pk {obj.pk}: {invalids_str}")

            if need_save:
                if not dry_run:
                    try:
                        obj.save()
                        saved += 1
                    except Exception as e:
                        logging.error(f"Failed to normalize number for {model_name} pk {obj.pk}: {e}")
                        with_error += 1
            else:
                if has_valid:
                    if has_invalid:
                        already_normalized_with_invalid += 1
                    else:
                        already_normalized_no_invalid += 1
                else:
                    with_all_invalid += 1

        logging.info(f"{saved} Saved")
        logging.info("Not saved:")
        logging.info(f"  {already_normalized_no_invalid} already normalized with all non-blank valid")
        logging.info(f"  {already_normalized_with_invalid} already normalized non-blanks with one+ invalid left")
        logging.info(f"  {with_all_invalid} all non-blank are invalid")
        logging.info(f"  {with_error} error saving\n")


if __name__ == "__main__":
    normalize_phone_numbers()
