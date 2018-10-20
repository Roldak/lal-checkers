procedure Test is
   type Point is record
      x : Integer;
      y : Integer;
   end record;

   b : Boolean;
   x : Point := (3, 1);
   y : Point := (4, 1);

   ptr : access Integer;
begin
   if b then
      ptr := x.x'Access;
   else
      ptr := y.x'Access;
   end if;

   ptr.all := 5;
end Ex1;
